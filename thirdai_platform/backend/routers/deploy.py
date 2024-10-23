import json
import os

pass
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urljoin

import requests
from auth.jwt import (
    AuthenticatedUser,
    now_plus_minutes,
    verify_access_token,
    verify_access_token_no_throw,
)
from backend.auth_dependencies import is_model_owner
from backend.startup_jobs import start_on_prem_generate_job
from backend.utils import (
    delete_nomad_job,
    get_model_from_identifier,
    get_model_status,
    get_platform,
    get_python_path,
    list_all_dependencies,
    logger,
    model_accessible,
    submit_nomad_job,
    thirdai_platform_dir,
    validate_license_info,
)
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from typing_extensions import Annotated

pass
from platform_common.pydantic_models.deployment import (
    DeploymentConfig,
    EnterpriseSearchOptions,
    NDBDeploymentOptions,
    UDTDeploymentOptions,
)
from platform_common.pydantic_models.training import ModelType
from platform_common.utils import response
from pydantic import BaseModel, Field
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


# TODO(Any): move args like llm_provider to model attributes.
async def deploy_single_model(
    model_id: str,
    memory: Optional[int],
    autoscaling_enabled: bool,
    autoscaler_max_count: int,
    genai_key: Optional[str],
    session: Session,
    user: schema.User,
):
    license_info = validate_license_info()

    try:
        model: schema.Model = session.query(schema.Model).get(model_id)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    if model.train_status != schema.Status.complete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Training isn't complete yet. Current status: {str(model.train_status)}",
        )

    if model.deploy_status in [
        schema.Status.starting,
        schema.Status.in_progress,
        schema.Status.complete,
    ]:
        return

    model.deploy_status = schema.Status.not_started
    session.commit()
    session.refresh(model)

    if not model_accessible(model, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to deploy this model.",
        )

    if not memory:
        if model.meta_data and model.meta_data.train:
            try:
                meta_data = json.loads(model.meta_data.train)
                size_in_memory = int(meta_data["size_in_memory"])
            except (json.JSONDecodeError, KeyError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to parse model metadata or missing 'size_in_memory'.",
                )
            memory = (size_in_memory // 1000000) + 1000  # MB required for deployment
        else:
            # This can be reached for models like enterprise-search which aren't
            # trained, and thus don't have training metadata with size_in_memory.
            # It can also be reached if a model is uploaded and not trained on platform.
            memory = 1000

    work_dir = os.getcwd()
    platform = get_platform()

    requires_on_prem_llm = False
    if model.type == ModelType.NDB:
        model_options = NDBDeploymentOptions(
            ndb_sub_type=model.sub_type,
            llm_provider=(
                model.get_attributes().get("llm_provider")
                or os.getenv("LLM_PROVIDER", "openai")
            ),
            genai_key=(genai_key or os.getenv("GENAI_KEY", "")),
        )
        requires_on_prem_llm = model_options.llm_provider == "on-prem"
    elif model.type == ModelType.UDT:
        model_options = UDTDeploymentOptions(udt_sub_type=model.sub_type)
    elif model.type == ModelType.ENTERPRISE_SEARCH:
        attributes = model.get_attributes()
        model_options = EnterpriseSearchOptions(
            retrieval_id=attributes["retrieval_id"],
            guardrail_id=attributes.get("guardrail_id", None),
        )
        requires_on_prem_llm = attributes.get("llm_provider") == "on-prem"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported model type '{model.type}'.",
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
            image_name=os.getenv("THIRDAI_PLATFORM_IMAGE_NAME"),
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(err),
        )

    if requires_on_prem_llm:
        llm_autoscaling_env = os.getenv("AUTOSCALING_ENABLED")
        if llm_autoscaling_env is not None:
            llm_autoscaling_enabled = llm_autoscaling_env.lower() == "true"
        else:
            llm_autoscaling_enabled = autoscaling_enabled
        await start_on_prem_generate_job(
            restart_if_exists=False, autoscaling_enabled=llm_autoscaling_enabled
        )


@deploy_router.post("/run", dependencies=[Depends(is_model_owner)])
async def deploy_model(
    model_identifier: str,
    memory: Optional[int] = None,
    autoscaling_enabled: bool = False,
    autoscaler_max_count: int = 1,
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

    try:
        model: schema.Model = get_model_from_identifier(model_identifier, session)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    for dependency in list_all_dependencies(model=model):
        try:
            await deploy_single_model(
                model_id=dependency.id,
                memory=memory,
                autoscaling_enabled=autoscaling_enabled,
                autoscaler_max_count=autoscaler_max_count,
                genai_key=genai_key,
                session=session,
                user=user,
            )
        except HTTPException as err:
            raise HTTPException(
                status_code=err.status_code,
                detail=f"Error deploying dependent model {dependency.name}: "
                + err.detail,
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

    deploy_status, reasons = get_model_status(model, train_status=False)
    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the deployment status",
        data={
            "deploy_status": deploy_status,
            "message": " ".join(reasons),
            "model_id": str(model.id),
        },
    )


class UsageStatOptions(BaseModel):
    duration: int  # In seconds
    num_datapoints: Annotated[int, Field(strict=True, gt=0)]  # Data points required

    @property
    def interval(self):
        return f"{self.duration // self.num_datapoints}s"

    def step_in_words(self):
        seconds_per_minute = 60
        seconds_per_hour = 60 * seconds_per_minute
        seconds_per_day = 24 * seconds_per_hour
        seconds_per_month = (
            30.44 * seconds_per_day
        )  # Average days in a month 30.44 days
        seconds_per_year = 12 * seconds_per_month

        temp = int(self.interval.rstrip("s"))
        years = temp // seconds_per_year
        temp %= seconds_per_year

        months = temp // seconds_per_month
        temp %= seconds_per_month

        days = temp // seconds_per_day
        temp %= seconds_per_day

        hours = temp // seconds_per_hour
        temp %= seconds_per_hour

        minutes = temp // seconds_per_minute
        seconds = temp % seconds_per_minute

        parts = []
        if years > 0:
            parts.append(f"{str(int(years)) + ' years' if years > 1 else 'year'}")

        for unit_name, unit_value in [
            ("month", months),
            ("day", days),
            ("hour", hours),
            ("minute", minutes),
            ("second", seconds),
        ]:
            if unit_value > 0:
                parts.append(
                    f"{int(unit_value)} {unit_name + 's' if unit_value > 1 else unit_name}"
                )

        return f"per {' '.join(parts)}"


@deploy_router.post("/usage-stats")
def usage_stats(
    model_identifier: str,
    usage_stat_option: UsageStatOptions,
    session: Session = Depends(get_session),
    # authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Get the usage stats of the deployment

    Parameters:
    - model_identifier: The identifier of the model.
    - duration: Duration for which stats are required. (In seconds)
    - step: Time difference between the intervals
    - session: The database session (dependency).
    - authenticated_user: The authenticated user (dependency).

    Example Usage:
    ```json
    {
        "model_identifier": "user123/model_name"
        "duration":"604800       # 1 week in seconds
        "steps": "1d"
    }
    ```
    Response data:
    ```json
    {
        Query per_day: {
                "2024-10-16 16:35:00": 7,
                "2024-10-17 16:35:00": 15,
                "2024-10-18 16:35:00": 8,
                "2024-10-19 16:35:00": 45,
                "2024-10-20 16:35:00": 51,
                "2024-10-21 16:35:00": 13,
                "2024-10-22 16:35:00": 15,
                "2024-10-23 16:35:00": 20,
            },
        Associate per_day: {
                "2024-10-16 16:35:00": 2,
                "2024-10-17 16:35:00": 2,
                "2024-10-18 16:35:00": 3,
                "2024-10-19 16:35:00": 0,
                "2024-10-20 16:35:00": 1,
                "2024-10-21 16:35:00": 0,
                "2024-10-22 16:35:00": 1,
                "2024-10-23 16:35:00": 3,
            },
        Upvote per_day: {
                "2024-10-16 16:35:00": 0,
                "2024-10-17 16:35:00": 1,
                "2024-10-18 16:35:00": 2,
                "2024-10-19 16:35:00": 4,
                "2024-10-20 16:35:00": 2,
                "2024-10-21 16:35:00": 0,
                "2024-10-22 16:35:00": 1,
                "2024-10-23 16:35:00": 1,
            }
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

    query_endpoint = urljoin(
        os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT"), "/victoriametric/api/v1/query_range"
    )

    # Common params
    end_time = datetime.now()
    start_time = end_time - timedelta(seconds=usage_stat_option.duration)
    params = {
        "start": int(start_time.timestamp()),
        "end": int(end_time.timestamp()),
        "step": usage_stat_option.interval,
    }

    worded_steps = usage_stat_option.step_in_words()
    metrics = (
        [
            (f"Query {worded_steps}", "ndb_query_count"),
            (f"Upvote {worded_steps}", "ndb_upvote_count"),
            (f"Associate {worded_steps}", "ndb_associate_count"),
        ]
        if model.type == "ndb"
        else [(f"Query {worded_steps}", "udt_predict")]
    )
    usage_data = {}
    for metric_name, metric_id in metrics:
        params["query"] = (
            f'sum(increase({metric_id}{{job="deployment-jobs", model_id="{model.id}"}}[{usage_stat_option.interval}]))'  # summing over all allocations
        )
        query_response = requests.get(query_endpoint, params=params)
        if query_response.status_code == 200:
            timeseries_data = query_response.json()["data"]["result"]

            if len(timeseries_data) == 0:
                # model was never deployed, so there will be no usage stats
                break

            usage_data[metric_name] = {}
            for timestamp, value in timeseries_data[0]["values"]:
                dt = datetime.fromtimestamp(timestamp)
                usage_data[metric_name][str(dt)] = value

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully retreived the usage stats",
        data=usage_data,
    )


@deploy_router.post("/update-status")
def update_deployment_status(
    model_id: str,
    new_status: schema.Status,
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

    model.deploy_status = new_status

    session.commit()

    return {"message": "successfully updated"}


def active_deployments_using_model(model_id: str, session: Session):
    return (
        session.query(schema.Model)
        .join(
            schema.ModelDependency,
            schema.Model.id == schema.ModelDependency.model_id,
        )
        .filter(
            schema.ModelDependency.dependency_id == model_id,
            schema.Model.deploy_status.in_(
                [
                    schema.Status.starting,
                    schema.Status.in_progress,
                    schema.Status.complete,
                ]
            ),
        )
        .count()
    )


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

    if active_deployments_using_model(model_id=model.id, session=session) > 0:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Unable to stop deployment for model {model_identifier} since it is used by other active workflows.",
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


@deploy_router.get("/active-deployment-count")
def active_deployment_count(model_id: str, session: Session = Depends(get_session)):
    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully retrieved number of deployments using model.",
        data={
            "deployment_count": active_deployments_using_model(
                model_id=model_id, session=session
            )
        },
    )


@deploy_router.post("/start-on-prem")
async def start_on_prem_job(
    model_name: str = "Llama-3.2-3B-Instruct-f16.gguf",
    restart_if_exists: bool = True,
    autoscaling_enabled: bool = True,
    cores_per_allocation: Optional[int] = None,
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    try:
        await start_on_prem_generate_job(
            model_name=model_name,
            restart_if_exists=restart_if_exists,
            autoscaling_enabled=autoscaling_enabled,
            cores_per_allocation=cores_per_allocation,
        )
    except Exception as e:
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start on prem LLM job with error: {str(e)}",
        )

    return response(
        status_code=status.HTTP_200_OK, message="On-prem job started successfully"
    )
