import json
import os
import traceback
from pathlib import Path
from typing import Optional, Union

from auth.jwt import (
    AuthenticatedUser,
    now_plus_minutes,
    verify_access_token,
    verify_access_token_no_throw,
)
from backend.auth_dependencies import is_model_owner
from backend.deployment_config import (
    DeploymentConfig,
    ModelType,
    NDBDeploymentOptions,
    UDTDeploymentOptions,
)
from backend.startup_jobs import start_on_prem_generate_job
from backend.utils import (
    delete_nomad_job,
    get_model_from_identifier,
    get_platform,
    get_python_path,
    get_root_absolute_path,
    thirdai_platform_dir,
    logger,
    model_accessible,
    response,
    submit_nomad_job,
    validate_license_info,
)
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

deploy_router = APIRouter()


def model_read_write_permissions(
    model_id: str,
    session: Session,
    authenticated_user: Union[AuthenticatedUser, HTTPException],
):
    """
    Determine read and write permissions for a model based on the user's access level.

    Parameters:
    - model_id: The ID of the model.
    - session: The database session.
    - authenticated_user: The authenticated user or HTTPException if authentication fails.

    Returns:
    - A tuple (read_permission: bool, write_permission: bool).
    """

    model: schema.Model = session.query(schema.Model).get(model_id)

    if not model:
        return False, False

    # If the user is not authenticated, check if the model is public
    if not isinstance(authenticated_user, AuthenticatedUser):
        return model.access_level == schema.Access.public, False

    user = authenticated_user.user
    permission = model.get_user_permission(user)

    return (
        permission == schema.Permission.read or permission == schema.Permission.write,
        permission == schema.Permission.write,
    )


def model_owner_permissions(
    model_id: str,
    session: Session,
    authenticated_user: Union[AuthenticatedUser, HTTPException],
):
    """
    Determine if the user has owner permissions for a model.

    Parameters:
    - model_id: The ID of the model.
    - session: The database session.
    - authenticated_user: The authenticated user or HTTPException if authentication fails.

    Returns:
    - A boolean indicating if the user has owner permissions.
    """
    model: schema.Model = session.query(schema.Model).get(model_id)

    if not isinstance(authenticated_user, AuthenticatedUser):
        return False

    return model.get_owner_permission(authenticated_user.user)


@deploy_router.get("/permissions/{model_id}")
def get_model_permissions(
    model_id: str,
    session: Session = Depends(get_session),
    authenticated_user: Union[AuthenticatedUser, HTTPException] = Depends(
        verify_access_token_no_throw
    ),
):
    """
    Get the permissions for a model.

    Parameters:
    - model_id: The ID of the model.
    - session: The database session (dependency).
    - authenticated_user: The authenticated user (dependency).

    Example Usage:
    ```json
    {
       "model_id" : "model_id",
    }
    ```
    """
    read, write = model_read_write_permissions(model_id, session, authenticated_user)
    override = model_owner_permissions(model_id, session, authenticated_user)
    exp = (
        authenticated_user.exp.isoformat()
        if isinstance(authenticated_user, AuthenticatedUser)
        else now_plus_minutes(minutes=120).isoformat()
    )

    return response(
        status_code=status.HTTP_200_OK,
        message=f"Successfully fetched user permissions for model with ID {model_id}",
        data={"read": read, "write": write, "exp": exp, "override": override},
    )


@deploy_router.post("/run", dependencies=[Depends(is_model_owner)])
def deploy_model(
    model_identifier: str,
    memory: Optional[int] = None,
    autoscaling_enabled: bool = False,
    autoscaler_max_count: int = 1,
    llm_provider: Optional[str] = None,
    genai_key: Optional[str] = None,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Deploy a model.

    Parameters:
    - model_identifier: The identifier of the model to deploy.
    - memory: Optional memory allocation for the deployment.
    - autoscaling_enabled: Whether autoscaling is enabled.
    - autoscaler_max_count: The maximum count for the autoscaler.
    - genai_key: Optional GenAI key.
    - session: The database session (dependency).
    - authenticated_user: The authenticated user (dependency).

    Example Usage:
    ```json
    {
        "deployment_name": "my_deployment",
        "model_identifier": "model_123",
        "memory": 2048,
        "autoscaling_enabled": true,
        "autoscaler_max_count": 5,
        "genai_key": "your_genai_key"
    }
    ```
    """
    user = authenticated_user.user

    license_info = validate_license_info()

    try:
        model: schema.Model = get_model_from_identifier(model_identifier, session)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    if model.train_status != schema.Status.complete:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Training isn't complete yet. Current status: {str(model.train_status)}",
        )

    if model.deploy_status in [
        schema.Status.starting,
        schema.Status.in_progress,
        schema.Status.complete,
    ]:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Deployment is already {model.deploy_status}.",
        )

    model.deploy_status = schema.Status.not_started
    session.commit()
    session.refresh(model)

    if not model_accessible(model, user):
        return response(
            status_code=status.HTTP_403_FORBIDDEN,
            message="You don't have access to deploy this model.",
        )

    if not memory:
        try:
            meta_data = json.loads(model.meta_data.train)
            size_in_memory = int(meta_data["size_in_memory"])
        except (json.JSONDecodeError, KeyError) as e:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Failed to parse model metadata or missing 'size_in_memory'.",
            )
        memory = (size_in_memory // 1000000) + 1000  # MB required for deployment

    work_dir = os.getcwd()
    platform = get_platform()

    if model.type == ModelType.NDB:
        model_options = NDBDeploymentOptions(
            ndb_sub_type=model.sub_type,
            llm_provider=(llm_provider or os.getenv("LLM_PROVIDER", "openai")),
            genai_key=(genai_key or os.getenv("GENAI_KEY", "")),
        )
    elif model.type == ModelType.UDT:
        model_options = UDTDeploymentOptions(udt_sub_type=model.sub_type)
    else:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Unsupported model type '{model.type}'.",
        )

    config = DeploymentConfig(
        model_id=str(model.id),
        model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT"),
        model_bazaar_dir=(
            os.getenv("SHARE_DIR", None) if platform == "local" else "/model_bazaar"
        ),
        license_key=license_info["boltLicenseKey"],
        autoscaling_enabled=autoscaling_enabled,
        model_options=model_options,
    )

    try:
        submit_nomad_job(
            str(Path(work_dir) / "backend" / "nomad_jobs" / "deployment_job.hcl.j2"),
            nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
            platform=platform,
            tag=os.getenv("TAG"),
            registry=os.getenv("DOCKER_REGISTRY"),
            docker_username=os.getenv("DOCKER_USERNAME"),
            docker_password=os.getenv("DOCKER_PASSWORD"),
            image_name=os.getenv("DEPLOY_IMAGE_NAME"),
            model_id=str(model.id),
            share_dir=os.getenv("SHARE_DIR", None),
            config_path=config.save_deployment_config(),
            autoscaling_enabled=("true" if autoscaling_enabled else "false"),
            autoscaler_max_count=str(autoscaler_max_count),
            memory=memory,
            python_path=get_python_path(),
            thirdai_platform_dir=thirdai_platform_dir(),
            app_dir="deployment_job",
            aws_access_key=(os.getenv("AWS_ACCESS_KEY", "")),
            aws_access_secret=(os.getenv("AWS_ACCESS_SECRET", "")),
        )

        model.deploy_status = schema.Status.starting
        session.commit()
    except Exception as err:
        model.deploy_status = schema.Status.failed
        session.commit()
        logger.info(traceback.format_exc())
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(err),
        )

    return response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Deployment is in-progress",
        data={
            "status": "queued",
            "model_identifier": model_identifier,
            "model_id": str(model.id),
        },
    )


@deploy_router.get("/status")
def deployment_status(
    model_identifier: str,
    session: Session = Depends(get_session),
):
    """
    Get the status of a deployment.

    Parameters:
    - model_identifier: The identifier of the model.
    - session: The database session (dependency).

    Example Usage:
    ```json
    {
        "model_identifier": "user123/model_name"
    }
    ```
    """
    try:
        model: schema.Model = get_model_from_identifier(model_identifier, session)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the deployment status",
        data={"deploy_status": model.deploy_status, "model_id": str(model.id)},
    )


@deploy_router.post("/update-status")
def update_deployment_status(
    model_id: str,
    status: schema.Status,
    session: Session = Depends(get_session),
):
    """
    Update the status of a deployment.

    Parameters:
    - model_id: The ID of the model.
    - status: The new status for the deployment.
    - session: The database session (dependency).

    Example Usage:
    ```json
    {
        "model_id": "model_id",
        "status": "in_progress"
    }
    ```
    """
    model: schema.Model = (
        session.query(schema.Model).filter(schema.Model.id == model_id).first()
    )

    if not model:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"No model with id {model_id}.",
        )

    model.deploy_status = status

    session.commit()

    return {"message": "successfully updated"}


@deploy_router.post("/stop", dependencies=[Depends(is_model_owner)])
def undeploy_model(
    model_identifier: str,
    session: Session = Depends(get_session),
):
    """
    Stop a running deployment.

    Parameters:
    - model_identifier: The identifier of the model to stop.
    - session: The database session (dependency).

    Example Usage:
    ```json
    {
        "model_identifier": "user123/model123"
    }
    ```
    """
    try:
        model: schema.Model = get_model_from_identifier(model_identifier, session)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    try:
        delete_nomad_job(
            job_id=f"deployment-{str(model.id)}",
            nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
        )
        model.deploy_status = schema.Status.stopped
        session.commit()

    except Exception as err:
        logger.info(str(err))
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(err),
        )

    return response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Service is shutting down",
        data={
            "status": "queued",
            "model_id": str(model.id),
        },
    )


@deploy_router.get("/info", dependencies=[Depends(is_model_owner)])
def get_deployment_info(
    model_identifier: str,
    session: Session = Depends(get_session),
):
    """
    Retrieve deployment information.

    Parameters:
    - model_identifier: The identifier of the model.

    Example Usage:
    ```json
    {
        "model_identifier": "username/modelname",
    }
    ```
    """
    try:
        model: schema.Model = get_model_from_identifier(model_identifier, session)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    # Prepare the response data
    deployment_info = {
        "name": model.name,
        "status": model.deploy_status,
        "model_id": str(model.id),
    }

    return response(
        status_code=status.HTTP_200_OK,
        message="Deployment info retrieved successfully",
        data=jsonable_encoder(deployment_info),
    )


@deploy_router.post("/start-on-prem")
async def start_on_prem_job(
    model_name: str = "qwen2-0_5b-instruct-fp16.gguf",
    restart_if_exists: bool = True,
    autoscaling_enabled: bool = True,
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    await start_on_prem_generate_job(
        model_name=model_name,
        restart_if_exists=restart_if_exists,
        autoscaling_enabled=autoscaling_enabled,
    )

    return response(
        status_code=status.HTTP_200_OK, message="On-prem job started successfully"
    )
