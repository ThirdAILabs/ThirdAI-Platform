import json
import os
import traceback
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from auth.jwt import AuthenticatedUser, verify_access_token
from backend.auth_dependencies import (
    global_admin_only,
    is_workflow_accessible,
    is_workflow_owner,
)
from backend.deployment_config import (
    DeploymentConfig,
    ModelType,
    NDBDeploymentOptions,
    UDTDeploymentOptions,
)
from backend.startup_jobs import start_on_prem_generate_job
from backend.utils import (
    delete_nomad_job,
    get_platform,
    get_python_path,
    get_workflow,
    list_workflow_models,
    load_json,
    response,
    submit_nomad_job,
    thirdai_platform_dir,
)
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from licensing.verify.verify_license import verify_license
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session, selectinload

workflow_router = APIRouter()


@workflow_router.get("/types")
def workflow_types(
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Get all workflow types.

    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.
      - `data` (dict): List of workflow types with their details.

    **Example Response**:
    ```json
    {
        "status_code": 200,
        "message": "Successfully got the workflow types",
        "data": {
            "types": [
                {
                    "id": "c1b1c5d7-8b8a-4f3b-a88b-2ec5a7a5f014",
                    "name": "semantic_search",
                    "description": "Semantic search workflow",
                    "model_requirements": [
                        [
                            {"component": "search", "type": "ndb"},
                            {"component": "guardrail", "type": "udt", "subtype": "token"}
                        ]
                    ]
                },
                ...
            ]
        }
    }
    ```
    """
    types = session.query(schema.WorkflowType).all()
    types_list = [
        {
            "id": str(t.id),
            "name": t.name,
            "description": t.description,
            "model_requirements": t.model_requirements,
        }
        for t in types
    ]
    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the workflow types",
        data={"types": jsonable_encoder(types_list)},
    )


@workflow_router.post("/create")
def create_workflow(
    name: str,
    type_name: str,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Create a new workflow.

    - **Parameters**:
      - `name` (str): Name of the workflow.
      - `type_name` (str): Name of the workflow type.
    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.
      - `data` (dict): ID of the newly created workflow.

    **Example Request**:
    ```json
    {
        "name": "MyWorkflow",
        "type_name": "semantic_search"
    }
    ```

    **Example Response**:
    ```json
    {
        "status_code": 200,
        "message": "Successfully added the workflow",
        "data": {"workflow_id": "f84b8f1d-76e1-4d9b-bb1a-8f8d5d6f1a3c"}
    }
    ```
    """
    user: schema.User = authenticated_user.user

    workflow: schema.Workflow = (
        session.query(schema.Workflow).filter_by(name=name, user_id=user.id).first()
    )

    if workflow:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Workflow with this name already exists for this user.",
        )

    workflow_type = session.query(schema.WorkflowType).filter_by(name=type_name).first()
    if not workflow_type:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Invalid workflow type name: {type_name}.",
        )

    new_workflow = schema.Workflow(
        name=name,
        type_id=workflow_type.id,
        user_id=user.id,
        status=schema.WorkflowStatus.inactive,
    )

    session.add(new_workflow)
    session.commit()
    session.refresh(new_workflow)

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully added the workflow",
        data={"workflow_id": str(new_workflow.id)},
    )


class WorkflowParams(BaseModel):
    workflow_id: str
    model_ids: List[str]
    components: List[str]  # Added to match components with models

    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "f84b8f1d-76e1-4d9b-bb1a-8f8d5d6f1a3c",
                "model_ids": ["model1_id", "model2_id"],
                "components": ["search", "guardrail"],  # Example components
            }
        }

        protected_namespaces = ()


@workflow_router.post("/add-models")
def add_models(
    body: WorkflowParams,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Add models to a workflow.

    - **Parameters**:
      - `body` (WorkflowParams): JSON body with workflow ID, model IDs, and components.
    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.
      - `data` (dict): List of models in the workflow.

    **Example Request**:
    ```json
    {
        "workflow_id": "f84b8f1d-76e1-4d9b-bb1a-8f8d5d6f1a3c",
        "model_ids": ["model1_id", "model2_id"],
        "components": ["search", "guardrail"]
    }
    ```

    **Example Response**:
    ```json
    {
        "status_code": 200,
        "message": "Models added to workflow successfully.",
        "data": {
            "models": [
                {"id": "model1_id", "name": "Model 1"...},
                {"id": "model2_id", "name": "Model 2"...}
            ]
        }
    }
    ```
    """
    workflow = get_workflow(session, body.workflow_id, authenticated_user)

    for model_id, component in zip(body.model_ids, body.components):
        model: schema.Model = session.query(schema.Model).get(model_id)
        if not model:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Model with ID {model_id} not found.",
            )

        if not model.get_user_permission(authenticated_user.user):
            return response(
                status_code=status.HTTP_403_FORBIDDEN,
                message=(
                    f"You do not have permission to add {model.name} "
                    f"(component: {component}). "
                ),
            )

        workflow_model: schema.WorkflowModel = (
            session.query(schema.WorkflowModel)
            .filter(
                schema.WorkflowModel.workflow_id == body.workflow_id,
                schema.WorkflowModel.model_id == model.id,
                schema.WorkflowModel.component == component,
            )
            .first()
        )

        if workflow_model:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Model {model.id} with component {component} already found in workflow.",
            )

        workflow_model = schema.WorkflowModel(
            workflow_id=workflow.id, model_id=model.id, component=component
        )
        session.add(workflow_model)

    session.commit()
    session.refresh(workflow)

    return response(
        status_code=status.HTTP_200_OK,
        message="Models added to workflow successfully.",
        data={"models": jsonable_encoder(list_workflow_models(workflow=workflow))},
    )


class WorkflowGenAIModel(BaseModel):
    workflow_id: str
    provider: str


@workflow_router.post("/set-gen-ai-provider")
def set_gen_ai_provider(
    body: WorkflowGenAIModel,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    workflow = get_workflow(session, body.workflow_id, authenticated_user)

    workflow.gen_ai_provider = body.provider
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="Successful",
        success=True,
    )


@workflow_router.post("/delete-models")
def delete_models(
    body: WorkflowParams,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Delete models from a workflow.

    - **Parameters**:
      - `body` (WorkflowParams): JSON body with workflow ID, model IDs, and components.
    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.
      - `data` (dict): List of models remaining in the workflow.

    **Example Request**:
    ```json
    {
        "workflow_id": "f84b8f1d-76e1-4d9b-bb1a-8f8d5d6f1a3c",
        "model_ids": ["model1_id", "model2_id"],
        "components": ["search", "guardrail"]
    }
    ```

    **Example Response**:
    ```json
    {
        "status_code": 200,
        "message": "Models deleted from workflow successfully.",
        "data": {
            "models": [
                {"id": "model3_id", "name": "Model 3"...}
            ]
        }
    }
    ```
    """
    workflow = get_workflow(session, body.workflow_id, authenticated_user)

    for model_id, component in zip(body.model_ids, body.components):
        model: schema.Model = session.query(schema.Model).get(model_id)
        if not model:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Model with ID {model_id} not found.",
            )

        workflow_model: schema.WorkflowModel = (
            session.query(schema.WorkflowModel)
            .filter(
                schema.WorkflowModel.workflow_id == body.workflow_id,
                schema.WorkflowModel.model_id == model.id,
                schema.WorkflowModel.component == component,
            )
            .first()
        )

        if not workflow_model:
            return response(
                status_code=status.HTTP_404_NOT_FOUND,
                message=f"Model {model.id} with component {component} not found in workflow.",
            )

        session.delete(workflow_model)

    session.commit()
    session.refresh(workflow)

    return response(
        status_code=status.HTTP_200_OK,
        message="Models deleted from workflow successfully.",
        data={"models": jsonable_encoder(list_workflow_models(workflow=workflow))},
    )


@workflow_router.post("/validate", dependencies=[Depends(is_workflow_owner)])
def validate_workflow(
    workflow_id: str,
    session: Session = Depends(get_session),
):
    """
    Validate a workflow to ensure it meets the model requirements.

    - **Parameters**:
      - `workflow_id` (str): ID of the workflow to validate.
    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.
      - `data` (dict): Validation issues or success message.

    **Example Request**:
    ```json
    {
        "workflow_id": "f84b8f1d-76e1-4d9b-bb1a-8f8d5d6f1a3c"
    }
    ```

    **Example Response**:
    ```json
    {
        "status_code": 200,
        "message": "Validation successful. All model requirements are met.",
        "data": {
            "models": [
                {"id": "model1", "name": "Model 1"...},
                {"id": "model2", "name": "Model 2"...}
            ]
        }
    }
    ```
    """
    workflow: schema.Workflow = session.query(schema.Workflow).get(workflow_id)

    if not workflow:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Workflow not found.",
        )

    workflow_models: List[schema.WorkflowModel] = workflow.workflow_models

    if not workflow_models:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="No models found in the workflow.",
        )

    workflow_type: schema.WorkflowType = workflow.workflow_type
    model_requirements = workflow_type.model_requirements

    all_requirements_valid = False
    issues_per_group = []

    # Loop over each requirement group
    for requirement_group in model_requirements:
        group_issues = defaultdict(list)

        for requirement in requirement_group:
            component = requirement["component"]
            model_type = requirement["type"]
            sub_type = requirement.get("subtype")

            matching_models = [
                wm
                for wm in workflow_models
                if wm.component == component
                and wm.model.type == model_type
                and (sub_type is None or wm.model.sub_type == sub_type)
            ]

            required_count = (
                1  # Since each requirement object represents exactly one required model
            )

            if len(matching_models) != required_count:
                group_issues[component].append(
                    f"Requires exactly {required_count} {model_type}(s) with component {component} and subtype {sub_type}, but found {len(matching_models)}."
                )

        if not group_issues:
            # If no issues in this group, the workflow is valid
            all_requirements_valid = True
            break
        else:
            # Store issues for this group
            issues_per_group.append(group_issues)

    if not all_requirements_valid:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Validation failed. Some model requirement groups have issues.",
            data={"issues": jsonable_encoder(issues_per_group)},
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Validation successful. All model requirements are met.",
        data={"models": jsonable_encoder(list_workflow_models(workflow))},
    )


@workflow_router.post("/update-status", dependencies=[Depends(is_workflow_owner)])
def update_workflow_status(
    workflow_id: str,
    new_status: schema.WorkflowStatus,
    session: Session = Depends(get_session),
):
    """
    Update the status of a workflow.

    - **Parameters**:
      - `workflow_id` (str): ID of the workflow to update.
      - `new_status` (str): New status to set for the workflow.
    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.

    **Example Request**:
    ```json
    {
        "workflow_id": "f84b8f1d-76e1-4d9b-bb1a-8f8d5d6f1a3c",
        "new_status": "active"
    }
    ```

    **Example Response**:
    ```json
    {
        "status_code": 200,
        "message": "Workflow status updated successfully.",
    }
    ```
    """
    workflow: schema.Workflow = session.query(schema.Workflow).get(workflow_id)

    if not workflow:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Workflow not found.",
        )

    try:
        workflow.status = new_status
        session.commit()
    except KeyError:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Invalid status: {new_status}.",
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Workflow status updated successfully.",
    )


@workflow_router.post("/stop", dependencies=[Depends(is_workflow_owner)])
def stop_workflow(
    workflow_id: str,
    session: Session = Depends(get_session),
):
    """
    Stop a workflow and undeploy models if necessary.

    - **Parameters**:
      - `workflow_id` (str): ID of the workflow to stop.
    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.

    **Example Request**:
    ```json
    {
        "workflow_id": "f84b8f1d-76e1-4d9b-bb1a-8f8d5d6f1a3c"
    }
    ```

    **Example Response**:
    ```json
    {
        "status_code": 200,
        "message": "Workflow stopped successfully."
    }
    ```
    """
    workflow: schema.Workflow = session.query(schema.Workflow).get(workflow_id)

    if not workflow:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Workflow not found.",
        )

    workflow_models: List[schema.WorkflowModel] = workflow.workflow_models

    for workflow_model in workflow_models:
        model: schema.Model = workflow_model.model
        if model.deploy_status in [schema.Status.complete, schema.Status.in_progress]:
            active_workflows_using_model = (
                session.query(schema.WorkflowModel)
                .join(schema.Workflow)
                .filter(
                    schema.WorkflowModel.model_id == model.id,
                    schema.Workflow.id != workflow_id,
                    schema.Workflow.status.in_([schema.WorkflowStatus.active]),
                )
                .count()
            )

            if active_workflows_using_model == 0:
                try:
                    delete_nomad_job(
                        job_id=f"deployment-{str(model.id)}",
                        nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
                    )
                    model.deploy_status = schema.Status.stopped
                    session.commit()
                except Exception as err:
                    workflow.status = schema.WorkflowStatus.inactive
                    session.commit()
                    return response(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        message=f"Failed to undeploy model {model.name}: {str(err)}",
                    )

    workflow.status = schema.WorkflowStatus.inactive
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="Workflow stopped successfully.",
    )


@workflow_router.post("/start", dependencies=[Depends(is_workflow_owner)])
async def start_workflow(
    workflow_id: str,
    autoscaling_enabled: bool = False,
    autoscaler_max_count: int = 1,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Start a workflow and deploy models if necessary.

    - **Parameters**:
      - `workflow_id` (str): ID of the workflow to start.
      - `autoscaling_enabled` (bool): Whether autoscaling should be enabled.
      - `autoscaler_max_count` (int): Maximum number of autoscalers.
    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.
      - `data` (dict): List of models in the workflow.

    **Example Request**:
    ```json
    {
        "workflow_id": "f84b8f1d-76e1-4d9b-bb1a-8f8d5d6f1a3c"
    }
    ```

    **Example Response**:
    ```json
    {
        "status_code": 202,
        "message": "Workflow started successfully.",
        "data": {
            "models": [
                {"id": "model1", "name": "Model 1"...},
                {"id": "model2", "name": "Model 2"...}
            ]
        }
    }
    ```
    """
    workflow: schema.Workflow = session.query(schema.Workflow).get(workflow_id)

    if not workflow:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Workflow not found.",
        )

    workflow.status = schema.WorkflowStatus.active
    session.commit()

    workflow_models: List[schema.WorkflowModel] = workflow.workflow_models

    if not workflow_models:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="No models found in the workflow.",
        )

    all_training_complete = True

    for workflow_model in workflow_models:
        model: schema.Model = workflow_model.model

        if model.train_status != schema.Status.complete:
            all_training_complete = False

    if not all_training_complete:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Cannot start workflow. Some models are not ready.",
            data={"models": jsonable_encoder(list_workflow_models(workflow))},
        )

    for workflow_model in workflow_models:
        model: schema.Model = workflow_model.model
        if model.deploy_status not in [
            schema.Status.starting,
            schema.Status.in_progress,
            schema.Status.complete,
        ]:
            if not model.get_user_permission(authenticated_user.user):
                return response(
                    status_code=status.HTTP_403_FORBIDDEN,
                    message=(
                        f"You do not have permission to deploy model {model.name} "
                        f"(component: {workflow_model.component}). "
                    ),
                )

            try:
                meta_data = json.loads(model.meta_data.train)
                size_in_memory = int(meta_data["size_in_memory"])
            except (json.JSONDecodeError, KeyError) as e:
                raise Exception(
                    "Failed to parse model metadata or missing 'size_in_memory'."
                )
            memory = (size_in_memory // 1000000) + 1000  # MB required for deployment

            work_dir = os.getcwd()
            platform = get_platform()

            if model.type == ModelType.NDB:
                model_options = NDBDeploymentOptions(
                    ndb_sub_type=model.sub_type,
                    llm_provider=workflow.gen_ai_provider
                    or os.getenv("LLM_PROVIDER", "openai"),
                    genai_key=os.getenv("GENAI_KEY", ""),
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
                    os.getenv("SHARE_DIR", None)
                    if platform == "local"
                    else "/model_bazaar"
                ),
                license_key=verify_license(
                    os.getenv(
                        "LICENSE_PATH",
                        "/model_bazaar/license/ndb_enterprise_license.json",
                    )
                )["boltLicenseKey"],
                autoscaling_enabled=autoscaling_enabled,
                model_options=model_options,
            )

            try:
                submit_nomad_job(
                    str(
                        Path(work_dir)
                        / "backend"
                        / "nomad_jobs"
                        / "deployment_job.hcl.j2"
                    ),
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
                    autoscaling_enabled=str(autoscaling_enabled).lower(),
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
                workflow.status = schema.WorkflowStatus.inactive
                session.commit()
                raise Exception(str(err))

    if workflow.gen_ai_provider == "on-prem":
        await start_on_prem_generate_job(restart_if_exists=False)

    return response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Workflow started successfully.",
        data={"models": jsonable_encoder(list_workflow_models(workflow))},
    )


@workflow_router.post("/feedbacks", dependencies=[Depends(is_workflow_owner)])
def workflow_feedbacks(
    workflow_id: str,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Fetches all the feedback collected on the deploed models in the workflow

    - **Parameters**:
      - `workflow_id` (str): ID of the workflow to start.
    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.
      - `data` (dict): Dict of feedbacks

    **Example Request**:
    ```json
    {
        "workflow_id": "f84b8f1d-76e1-4d9b-bb1a-8f8d5d6f1a3c"
    }
    ```

    **Example Response**:
    ```json
    {
        "status_code": 200,
        "message": "Retrieved model feedbacks.",
        "data": {
            "upvotes": [
                {"chunk_id": 17, "query": "query to one of the model"}
                {"chunk_id": 188, "query": "query to one of the model"}
                ..
            ],
            "associates": [
                {"source": "This is the source1", "target": "This is the target1"}
                {"source": "This is the source2", "target": "This is the target2"}
                ..
            ]
        }
    }
    ```
    """

    workflow: schema.Workflow = session.query(schema.Workflow).get(workflow_id)

    if not workflow:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Workflow not found.",
        )

    workflow_models: List[schema.WorkflowModel] = list(
        filter(
            lambda model: model.deploy_status == schema.Status.complete,
            workflow.workflow_models,
        )
    )

    if not workflow_models:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="No deployed models found in the workflow.",
        )
    platform = get_platform()
    model_bazaar_dir = (
        os.getenv("SHARE_DIR", None) if platform == "local" else "/model_bazaar"
    )

    accumlated_stats = defaultdict(list)

    for workflow_model in workflow_models:
        model: schema.Model = workflow_model.model

        deployment_dir = os.path.join(
            model_bazaar_dir, "models", str(model.id), "deployment", "data", "feedback"
        )
        if not os.path.exists(deployment_dir):
            continue

        for alloc_dir_entry in os.scandir(deployment_dir):
            stats_file_path = os.path.join(alloc_dir_entry.path, "last_stats.json")
            if os.path.join(stats_file_path):
                stats = load_json(stats_file_path)

                for event_type, entries in stats.items():
                    accumlated_stats[event_type].extend(entries)

    # sort event's entries based on timestamp
    for key in accumlated_stats:
        accumlated_stats[key].sort(
            key=lambda x: datetime.strptime(x["timestamp"], "%Y-%m-%d %H-%M-%S")
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully retrieved the feedback stats",
        data=accumlated_stats,
    )


class WorkflowTypeParams(BaseModel):
    name: str
    description: str
    model_requirements: List[List[dict]]  # Updated to list of list of dictionaries

    @validator("name")
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty.")
        return v

    @validator("model_requirements")
    def requirements_must_not_be_empty(cls, v):
        if not v:
            raise ValueError("Model requirements cannot contain empty lists.")
        for requirement_group in v:
            if not requirement_group:
                raise ValueError("Model requirements cannot contain empty groups.")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "semantic_search",
                "description": "Semantic search workflow",
                "model_requirements": [
                    [
                        {"component": "search", "type": "ndb"},
                        {"component": "guardrail", "type": "udt", "subtype": "token"},
                    ],
                    [
                        {"component": "search", "type": "ndb"},
                        {"component": "guardrail", "type": "udt", "subtype": "text"},
                    ],
                ],
            }
        }

        protected_namespaces = ()


@workflow_router.post("/add-type", dependencies=[Depends(global_admin_only)])
def add_workflow_type(
    params: WorkflowTypeParams,
    session: Session = Depends(get_session),
):
    """
    Add a new workflow type.

    - **Parameters**:
      - `params` (WorkflowTypeParams): JSON body with workflow type details.
    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.
      - `data` (dict): ID and name of the newly created workflow type.

    **Example Request**:
    ```json
    {
        "name": "semantic_search",
        "description": "Semantic search workflow",
        "model_requirements": [
            [
                {"component": "search", "type": "ndb"},
                {"component": "guardrail", "type": "udt", "subtype": "token"}
            ]
        ]
    }
    ```

    **Example Response**:
    ```json
    {
        "status_code": 200,
        "message": "Successfully added the workflow type",
        "data": {
            "id": "c1b1c5d7-8b8a-4f3b-a88b-2ec5a7a5f014",
            "name": "semantic_search"
        }
    }
    ```
    """
    existing_type = (
        session.query(schema.WorkflowType).filter_by(name=params.name).first()
    )
    if existing_type:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Workflow type with this name already exists.",
        )

    new_workflow_type = schema.WorkflowType(
        name=params.name,
        description=params.description,
        model_requirements=params.model_requirements,
    )
    session.add(new_workflow_type)
    session.commit()
    session.refresh(new_workflow_type)

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully added the workflow type",
        data={"id": str(new_workflow_type.id), "name": new_workflow_type.name},
    )


@workflow_router.post("/delete-type", dependencies=[Depends(global_admin_only)])
def delete_workflow_type(
    type_id: str,
    session: Session = Depends(get_session),
):
    """
    Delete a workflow type.

    - **Parameters**:
      - `type_id` (str): ID of the workflow type to delete.
    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.

    **Example Request**:
    ```json
    {
        "type_id": "c1b1c5d7-8b8a-4f3b-a88b-2ec5a7a5f014"
    }
    ```

    **Example Response**:
    ```json
    {
        "status_code": 200,
        "message": "Successfully deleted the workflow type"
    }
    ```
    """
    workflow_type = session.query(schema.WorkflowType).filter_by(id=type_id).first()
    if not workflow_type:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Workflow type not found.",
        )

    session.delete(workflow_type)
    session.commit()

    return response(
        status_code=status.HTTP_200_OK, message="Successfully deleted the workflow type"
    )


@workflow_router.get("/details", dependencies=[Depends(is_workflow_accessible)])
def get_workflow_details(
    workflow_id: str,
    session: Session = Depends(get_session),
):
    """
    Get detailed information about a specific workflow.

    - **Parameters**:
      - `workflow_id` (str): ID of the workflow.
    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.
      - `data` (dict): Detailed information about the workflow.

    **Example Request**:
    ```json
    {
        "workflow_id": "f84b8f1d-76e1-4d9b-bb1a-8f8d5d6f1a3c"
    }
    ```

    **Example Response**:
    ```json
    {
        "status_code": 200,
        "message": "Workflow details retrieved successfully.",
        "data": {
            "id": "f84b8f1d-76e1-4d9b-bb1a-8f8d5d6f1a3c",
            "name": "MyWorkflow",
            "type": "semantic_search",
            "type_id": "c1b1c5d7-8b8a-4f3b-a88b-2ec5a7a5f014",
            "status": "in_progress",
            "models": [
                {"id": "model1", "name": "Model 1", ...},
                {"id": "model2", "name": "Model 2", ...}
            ],
            ...
        }
    }
    ```
    """
    workflow: schema.Workflow = session.query(schema.Workflow).get(workflow_id)

    if not workflow:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Workflow not found.",
        )

    workflow_data = {
        "id": str(workflow.id),
        "name": workflow.name,
        "type": workflow.workflow_type.name,
        "type_id": str(workflow.type_id),
        "gen_ai_provider": workflow.gen_ai_provider,
        "status": workflow.status,
        "publish_date": str(workflow.published_date),
        "models": jsonable_encoder(list_workflow_models(workflow=workflow)),
    }

    return response(
        status_code=status.HTTP_200_OK,
        message="Workflow details retrieved successfully.",
        data=jsonable_encoder(workflow_data),
    )


@workflow_router.post("/delete", dependencies=[Depends(is_workflow_owner)])
def delete_workflow(
    workflow_id: str,
    session: Session = Depends(get_session),
):
    """
    Delete a workflow by its ID.

    - **Parameters**:
      - `workflow_id` (str): ID of the workflow to delete.
    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.
    """
    try:
        workflow: schema.Workflow = session.query(schema.Workflow).get(workflow_id)

        if not workflow:
            return response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Workflow not found.",
            )

        session.delete(workflow)
        session.commit()

    except Exception as err:
        traceback.print_exc()
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Failed to delete the workflow due to {err}",
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Workflow deleted successfully.",
    )


@workflow_router.get("/status", dependencies=[Depends(is_workflow_accessible)])
def get_workflow_status(
    workflow_id: str,
    session: Session = Depends(get_session),
):
    """
    Get the current status of a specific workflow.

    - **Parameters**:
      - `workflow_id` (str): ID of the workflow.
    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.
      - `data` (dict): The current status of the workflow.

    **Example Request**:
    ```json
    {
        "workflow_id": "f84b8f1d-76e1-4d9b-bb1a-8f8d5d6f1a3c"
    }
    ```

    **Example Response**:
    ```json
    {
        "status_code": 200,
        "message": "Workflow status retrieved successfully.",
        "data": {
            "workflow_id": "f84b8f1d-76e1-4d9b-bb1a-8f8d5d6f1a3c",
            "status": "in_progress"
        }
    }
    ```
    """
    workflow: schema.Workflow = session.query(schema.Workflow).get(workflow_id)

    if not workflow:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Workflow not found.",
        )

    workflow_status = {
        "workflow_id": str(workflow.id),
        "status": workflow.status,
    }

    return response(
        status_code=status.HTTP_200_OK,
        message="Workflow status retrieved successfully.",
        data=jsonable_encoder(workflow_status),
    )


@workflow_router.get("/list")
def list_accessible_workflows(
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    List all workflows accessible to the authenticated user.

    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.
      - `data` (dict): List of workflows accessible to the user.
    """
    user: schema.User = authenticated_user.user

    # Perform a single query to fetch workflows and eagerly load their models
    workflows = (
        session.query(schema.Workflow)
        .outerjoin(schema.Workflow.workflow_models)
        .options(
            selectinload(schema.Workflow.workflow_models).selectinload(
                schema.WorkflowModel.model
            )
        )  # Eager loading workflow models and associated model data
        .all()
    )

    filtered_workflows = [
        workflow for workflow in workflows if workflow.can_access(user)
    ]

    # Apply the can_access check on the remaining workflows
    accessible_workflows = [
        workflow for workflow in filtered_workflows if workflow.can_access(user)
    ]

    workflow_list = [
        {
            "id": str(workflow.id),
            "name": workflow.name,
            "type": workflow.workflow_type.name,
            "type_id": str(workflow.type_id),
            "status": workflow.status,
            "models": jsonable_encoder(list_workflow_models(workflow=workflow)),
            "publish_date": str(workflow.published_date),
            "gen_ai_provider": workflow.gen_ai_provider,
            "created_by": {
                "id": str(workflow.user.id),
                "username": workflow.user.username,
                "email": workflow.user.email,
            },
        }
        for workflow in accessible_workflows
    ]

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully retrieved accessible workflows.",
        data=jsonable_encoder(workflow_list),
    )


@workflow_router.get("/type")
def get_workflow_type_details(
    type_id: str,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Get detailed information about a specific workflow type.

    - **Parameters**:
      - `type_id` (str): The ID of the workflow type to retrieve.
    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.
      - `data` (dict): Detailed information about the workflow type.

    **Example Request**:
    ```json
    {
        "type_id": "c1b1c5d7-8b8a-4f3b-a88b-2ec5a7a5f014"
    }
    ```

    **Example Response**:
    ```json
    {
        "status_code": 200,
        "message": "Workflow type details retrieved successfully.",
        "data": {
            "id": "c1b1c5d7-8b8a-4f3b-a88b-2ec5a7a5f014",
            "name": "semantic_search",
            "description": "Semantic search workflow",
            "model_requirements": [
                [
                    {"component": "search", "type": "ndb"},
                    {"component": "guardrail", "type": "udt", "subtype": "token"}
                ]
            ]
        }
    }
    ```
    """
    workflow_type = session.query(schema.WorkflowType).filter_by(id=type_id).first()

    if not workflow_type:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Workflow type not found.",
        )

    workflow_type_data = {
        "id": str(workflow_type.id),
        "name": workflow_type.name,
        "description": workflow_type.description,
        "model_requirements": workflow_type.model_requirements,
    }

    return response(
        status_code=status.HTTP_200_OK,
        message="Workflow type details retrieved successfully.",
        data=jsonable_encoder(workflow_type_data),
    )


@workflow_router.get("/count")
def get_workflow_count(
    model_id: str,
    status_filter: Optional[schema.WorkflowStatus] = None,
    session: Session = Depends(get_session),
):
    """
    Get the count of workflows associated with a specific model by its identifier and status.

    - **Parameters**:
      - `model_id` (str): The identifier of the model to check.
      - `status_filter` (WorkflowStatus, optional): The status filter to apply (e.g., "active", "inactive").
        If not provided, counts all workflows.

    - **Returns**:
      - `status_code` (int): HTTP status code.
      - `message` (str): Response message.
      - `data` (dict): Count of workflows associated with the model.

    **Example Request**:
    ```json
    {
        "model_id": "UUID of the model",
        "status_filter": "active"
    }
    ```
    **Example Response**:
    ```json
    {
        "status_code": 200,
        "message": "Workflows count retrieved successfully.",
        "data": {
            "workflows_count": 3
        }
    }
    ```
    """
    model: schema.Model = session.query(schema.Model).get(model_id)

    if not model:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Model not found.",
        )

    # Base query to count workflows associated with the model
    query = (
        session.query(schema.Workflow)
        .join(schema.Workflow.workflow_models)
        .filter(schema.WorkflowModel.model_id == model.id)
    )

    # Apply status filter based on the value of status_filter
    if status_filter:
        query = query.filter(schema.Workflow.status == status_filter)

    workflows_count = query.count()

    return response(
        status_code=status.HTTP_200_OK,
        message="Workflows count retrieved successfully.",
        data={"workflows_count": workflows_count},
    )
