import os
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from auth.jwt import (
    AuthenticatedUser,
    now_plus_minutes,
    verify_access_token,
    verify_access_token_no_throw,
)
from backend.utils import (
    delete_nomad_job,
    get_deployment,
    get_empty_port,
    get_model,
    get_model_from_identifier,
    get_platform,
    get_python_path,
    get_root_absolute_path,
    logger,
    model_accessible,
    parse_deployment_identifier,
    response,
    submit_nomad_job,
    update_json,
    update_json_list,
    validate_name,
)
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from licensing.verify.verify_license import valid_job_allocation, verify_license
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

deploy_router = APIRouter()


def deployment_read_write_permissions(
    deployment_id: str,
    session: Session,
    authenticated_user: Union[AuthenticatedUser, HTTPException],
):
    """
    Determine read and write permissions for a deployment based on the user's access level.

    Parameters:
    - deployment_id: The ID of the deployment.
    - session: The database session.
    - authenticated_user: The authenticated user or HTTPException if authentication fails.

    Returns:
    - A tuple (read_permission: bool, write_permission: bool).
    """
    deployment: schema.Deployment = (
        session.query(schema.Deployment)
        .options(joinedload(schema.Deployment.user))
        .get(deployment_id)
    )
    access_level = session.query(schema.Model).get(deployment.model_id).access_level
    deployment_is_public = access_level == schema.Access.public

    if not isinstance(authenticated_user, AuthenticatedUser):
        if deployment_is_public:
            return True, False
        return False, False

    current_user: schema.User = authenticated_user.user
    if deployment.user_id == current_user.id:
        return True, True

    if deployment_is_public:
        return True, False

    deployment_is_protected = access_level == schema.Access.protected
    user_is_in_deployment_domain = deployment.user.domain == current_user.domain
    if deployment_is_protected and user_is_in_deployment_domain:
        return True, False

    return False, False


def deployment_owner_permissions(
    deployment_id: str,
    session: Session,
    authenticated_user: Union[AuthenticatedUser, HTTPException],
):
    """
    Determine if the user has owner permissions for a deployment.

    Parameters:
    - deployment_id: The ID of the deployment.
    - session: The database session.
    - authenticated_user: The authenticated user or HTTPException if authentication fails.

    Returns:
    - A boolean indicating if the user has owner permissions.
    """
    deployment: schema.Deployment = (
        session.query(schema.Deployment)
        .options(joinedload(schema.Deployment.user))
        .get(deployment_id)
    )

    if not isinstance(authenticated_user, AuthenticatedUser):
        return False

    current_user: schema.User = authenticated_user.user

    model: schema.Model = session.query(schema.Model).get(deployment.model_id)

    return model.user_id == current_user.id


@deploy_router.get("/permissions/{deployment_id}")
def get_deployment_permissions(
    deployment_id: str,
    session: Session = Depends(get_session),
    authenticated_user=Depends(verify_access_token_no_throw),
):
    """
    Get the permissions for a deployment.

    Parameters:
    - deployment_id: The ID of the deployment.
    - session: The database session (dependency).
    - authenticated_user: The authenticated user (dependency).

    Returns:
    - A JSON response with the read, write, and override permissions and the token expiration time.
    """
    read, write = deployment_read_write_permissions(
        deployment_id, session, authenticated_user
    )
    override = deployment_owner_permissions(deployment_id, session, authenticated_user)
    exp = (
        authenticated_user.exp.isoformat()
        if isinstance(authenticated_user, AuthenticatedUser)
        else now_plus_minutes(minutes=120).isoformat()
    )

    return response(
        status_code=status.HTTP_200_OK,
        message=f"Successfully fetched user permissions for deployment with ID {deployment_id}",
        data={"read": read, "write": write, "exp": exp, "override": override},
    )


@deploy_router.post("/run")
def deploy_model(
    deployment_name: str,
    model_identifier: str,
    memory: Optional[int] = None,
    autoscaling_enabled: bool = False,
    autoscaler_max_count: int = 1,
    genai_key: Optional[str] = None,
    use_llm_guardrail: Optional[bool] = None,
    token_model_identifier: Optional[str] = None,
    type: Optional[str] = None,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Deploy a model.

    Parameters:
    - deployment_name: str - The name of the deployment.
    - model_identifier: str - The identifier of the model to deploy.
    - memory: Optional[int] - Optional memory allocation for the deployment.
    - autoscaling_enabled: bool - Whether autoscaling is enabled.
    - autoscaler_max_count: int - The maximum count for the autoscaler.
    - genai_key: Optional[str] - Optional GenAI key.
    - use_llm_guardrail: bool - Whether to enable or disable LLM guardrail.
    - token_model_identifier: Optional[str] - The identifier of the token model to use for PII detection.
    - session: Session - The database session (dependency).
    - authenticated_user: AuthenticatedUser - The authenticated user (dependency).

    Returns:
    - JSONResponse: A JSON response indicating the status of the deployment.
    """
    user: schema.User = authenticated_user.user

    try:
        license_info = verify_license(
            os.getenv(
                "LICENSE_PATH", "/model_bazaar/license/ndb_enterprise_license.json"
            )
        )
        if not valid_job_allocation(license_info, os.getenv("NOMAD_ENDPOINT")):
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Resource limit reached, cannot allocate new jobs.",
            )
    except Exception as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"License is not valid. {str(e)}",
        )

    try:
        validate_name(deployment_name)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Deployment name is not valid.",
        )

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

    duplicate_deployment: schema.Deployment = get_deployment(
        session, deployment_name, user.id, model.id
    )

    if duplicate_deployment:
        if duplicate_deployment.status != schema.Status.stopped:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Deployment already running",
            )
        else:
            duplicate_deployment.status = schema.Status.not_started
            session.commit()
            deployment = duplicate_deployment
    else:
        deployment_identifier = f"{model_identifier}:{user.username}/{deployment_name}"
        deployment_id = uuid.uuid3(uuid.NAMESPACE_URL, deployment_identifier)
        deployment = schema.Deployment(
            id=deployment_id,
            model_id=model.id,
            user_id=user.id,
            name=deployment_name,
            status=schema.Status.not_started,
        )
        session.add(deployment)
        session.commit()
        session.refresh(deployment)

    if not model_accessible(model, user):
        return response(
            status_code=status.HTTP_403_FORBIDDEN,
            message="You don't have access to deploy this model.",
        )

    if not memory:
        memory = (
            int(model.meta_data.train["size_in_memory"]) // 1000000
        ) + 1000  # MB required for deployment

    if token_model_identifier:
        try:
            token_model: schema.Model = get_model_from_identifier(
                token_model_identifier, session
            )
        except Exception as error:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=str(error),
            )

        if token_model.type != "udt" or token_model.sub_type != "token":
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="You cannot use this model for PII detection.",
            )

    # Update or retain metadata fields with defaults
    metadata = deployment.metadata_json or {}
    metadata["deploy_type"] = type if type is not None else metadata.get("type", "")
    metadata["use_llm_guardrail"] = (
        use_llm_guardrail
        if use_llm_guardrail is not None
        else metadata.get("use_llm_guardrail", False)
    )

    if token_model_identifier:
        metadata["token_model_id"] = str(token_model.id)
    elif "token_model_id" not in metadata:
        metadata["token_model_id"] = None

    deployment.metadata_json = metadata

    model_metadata: schema.MetaData = model.meta_data
    if model_metadata:
        model_metadata.general = update_json(model_metadata.general, metadata)
    else:
        new_metadata = schema.MetaData(
            model_id=model.id,
            general=metadata,
        )
        session.add(new_metadata)

    session.commit()

    try:
        work_dir = os.getcwd()
        platform = get_platform()

        submit_nomad_job(
            str(Path(work_dir) / "backend" / "nomad_jobs" / "deployment_job.hcl.j2"),
            nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
            platform=platform,
            tag=os.getenv("TAG"),
            registry=os.getenv("DOCKER_REGISTRY"),
            docker_username=os.getenv("DOCKER_USERNAME"),
            docker_password=os.getenv("DOCKER_PASSWORD"),
            image_name=os.getenv("DEPLOY_IMAGE_NAME"),
            port=None if platform == "docker" else get_empty_port(),
            deployment_app_dir=str(get_root_absolute_path() / "deployment_job"),
            model_id=str(model.id),
            deployment_id=str(deployment.id),
            model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT"),
            share_dir=os.getenv("SHARE_DIR", None),
            license_key=license_info["boltLicenseKey"],
            genai_key=(genai_key or os.getenv("GENAI_KEY", "")),
            autoscaling_enabled=("true" if autoscaling_enabled else "false"),
            autoscaler_max_count=str(autoscaler_max_count),
            memory=memory,
            type=model.type,
            sub_type=model.sub_type,
            python_path=get_python_path(),
            aws_access_key=(os.getenv("AWS_ACCESS_KEY", "")),
            aws_access_secret=(os.getenv("AWS_ACCESS_SECRET", "")),
            llm_guardrail=("true" if metadata.get("use_llm_guardrail") else "false"),
            token_model_id=(metadata.get("token_model_id") or "NONE"),
        )

        deployment.status = schema.Status.in_progress
        session.commit()

    except Exception as err:
        deployment.status = schema.Status.failed
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
            "deployment_name": deployment_name,
            "deployment_id": str(deployment.id),
        },
    )


@deploy_router.get("/status")
def deployment_status(
    deployment_identifier: str,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Get the status of a deployment.

    Parameters:
    - deployment_identifier: The identifier of the deployment.
    - session: The database session (dependency).
    - authenticated_user: The authenticated user (dependency).

    Returns:
    - A JSON response with the deployment status and ID.
    """
    (
        model_username,
        model_name,
        deployment_username,
        deployment_name,
    ) = parse_deployment_identifier(deployment_identifier)

    deployment_user: schema.User = (
        session.query(schema.User)
        .filter(schema.User.username == deployment_username)
        .first()
    )

    model: schema.Model = get_model(session, model_username, model_name)
    if not model:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="No deployment with this identifier",
        )

    deployment: schema.Deployment = get_deployment(
        session, deployment_name, deployment_user.id, model.id
    )
    if not deployment:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="No deployment with this identifier",
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the deployment status",
        data={"status": deployment.status, "deployment_id": str(deployment.id)},
    )


@deploy_router.post("/update-status")
def deployment_status(
    deployment_id: str,
    status: schema.Status,
    session: Session = Depends(get_session),
):
    """
    Update the status of a deployment.

    Parameters:
    - deployment_id: The ID of the deployment.
    - status: The new status for the deployment.
    - session: The database session (dependency).

    Returns:
    - A JSON response indicating the update status.
    """
    deployment: schema.Deployment = (
        session.query(schema.Deployment)
        .filter(schema.Deployment.id == deployment_id)
        .first()
    )

    if not deployment:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"No deployment with id {deployment_id}.",
        )

    deployment.status = status

    session.commit()

    return {"message": "successfully updated"}


@deploy_router.get("/model-name")
def deployment_model_Name(
    deployment_id: str,
    session: Session = Depends(get_session),
):
    deployment: schema.Deployment = (
        session.query(schema.Deployment)
        .filter(schema.Deployment.id == deployment_id)
        .first()
    )

    if not deployment:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"No deployment with id {deployment_id}.",
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the deployment name",
        data={"name": deployment.name, "deployment_id": str(deployment.id)},
    )


@deploy_router.post("/stop")
def undeploy_model(
    deployment_identifier: str,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Stop a running deployment.

    Parameters:
    - deployment_identifier: The identifier of the deployment to stop.
    - session: The database session (dependency).
    - authenticated_user: The authenticated user (dependency).

    Returns:
    - A JSON response indicating the stop status of the deployment.
    """
    (
        model_username,
        model_name,
        deployment_username,
        deployment_name,
    ) = parse_deployment_identifier(deployment_identifier)

    deployment_user: schema.User = (
        session.query(schema.User)
        .filter(schema.User.username == deployment_username)
        .first()
    )

    model: schema.Model = get_model(session, model_username, model_name)
    if not model:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="No deployment with this identifier",
        )

    deployment: schema.Deployment = get_deployment(
        session, deployment_name, deployment_user.id, model.id
    )

    if not deployment:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="No deployment with this identifier",
        )

    try:
        delete_nomad_job(
            job_id=f"deployment-{str(deployment.id)}",
            nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
        )
        deployment.status = schema.Status.stopped
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
            "deployment_identifier": deployment_identifier,
        },
    )


class LogData(BaseModel):
    deployment_id: str
    action: str
    train_samples: List[Dict[str, str]]
    used: bool


@deploy_router.post("/log")
def log_results(
    log_data: LogData,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Log training results for a deployment.

    Parameters:
    - log_data: The log data to save (body).
    - session: The database session (dependency).
    - authenticated_user: The authenticated user (dependency).

    Returns:
    - A JSON response indicating the log entry status.
    """
    user: schema.User = authenticated_user.user
    deployment: schema.Deployment = (
        session.query(schema.Deployment)
        .filter(schema.Deployment.id == log_data.deployment_id)
        .first()
    )

    if not deployment:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="No deployment with this id",
        )

    log_entry = (
        session.query(schema.Log)
        .filter(
            schema.Log.deployment_id == log_data.deployment_id,
            schema.Log.user_id == user.id,
            schema.Log.action == log_data.action,
        )
        .first()
    )

    new_log = {
        "train_samples": log_data.train_samples,
        "used": str(log_data.used),
        "timestamp": str(datetime.utcnow().isoformat()),
    }

    if not log_entry:
        log_entry = schema.Log(
            deployment_id=deployment.id,
            user_id=user.id,
            action=log_data.action,
        )
        session.add(log_entry)
        session.commit()
        session.refresh(log_entry)

    log_entry.log_entries = update_json_list(log_entry.log_entries, new_log)
    log_entry.count += len(log_data.train_samples)

    session.commit()

    return {"message": "Log entry added successfully"}


@deploy_router.get("/list-deployments")
def list_deployments(
    deployment_id: Optional[str] = None,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    List existing deployments or fetch a specific deployment by ID.

    Returns deployment information.
    """
    user: schema.User = authenticated_user.user

    query = session.query(schema.Deployment).join(
        schema.Model, schema.Deployment.model_id == schema.Model.id
    )

    if deployment_id:
        query = query.filter(
            schema.Deployment.id == deployment_id,
            or_(
                schema.Deployment.user_id == user.id,
                schema.Model.access_level == schema.Access.public,
            ),
        )
        deployment = query.first()

        if not deployment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
            )

        results = [
            {
                "name": deployment.name,
                "deployment_username": deployment.user.username,
                "model_name": deployment.model.name,
                "model_username": deployment.model.user.username,
                "status": deployment.status,
                "metadata": deployment.metadata_json,
                "modelID": str(deployment.model_id),
            }
        ]
    else:
        deployments: List[schema.Deployment] = query.filter(
            or_(
                schema.Deployment.user_id == user.id,
                schema.Model.access_level == schema.Access.public,
            )
        ).all()

        results = [
            {
                "name": deployment.name,
                "deployment_username": deployment.user.username,
                "model_name": deployment.model.name,
                "model_username": deployment.model.user.username,
                "status": deployment.status,
                "metadata": deployment.metadata_json,
            }
            for deployment in deployments
        ]

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully fetched deployments",
        data=jsonable_encoder(results),
    )


@deploy_router.post("/update-metadata")
def update_metadata(
    deployment_id: str,
    metadata: Dict[str, str],
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Update the metadata of a deployment.

    Parameters:
    - deployment_id: str - The ID of the deployment to update.
    - metadata: Dict[str, str] - The new metadata to set.
    - session: Session - The database session (dependency).
    - authenticated_user: AuthenticatedUser - The authenticated user (dependency).

    Returns:
    - JSONResponse: A JSON response indicating the status of the update.
    """
    # Fetch the deployment by ID
    deployment = session.query(schema.Deployment).filter_by(id=deployment_id).first()

    # Check if deployment exists
    if not deployment:
        return response(
            status_code=status.HTTP_404_NOT_FOUND, message="Deployment not found."
        )

    deployment.metadata_json = update_json(deployment.metadata_json, metadata)
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="Deployment metadata updated successfully.",
        data={"deployment_id": deployment_id, "metadata": deployment.metadata_json},
    )
