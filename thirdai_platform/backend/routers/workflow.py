import uuid
from typing import List, Optional

from backend.auth_dependencies import get_current_user
from backend.utils import get_model, validate_name
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, status
from platform_common.pydantic_models.training import ModelType, UDTSubType
from platform_common.utils import response
from pydantic import BaseModel
from sqlalchemy.orm import Session

workflow_router = APIRouter()


class EnterpriseSearchOptions(BaseModel):
    retrieval_id: str
    guardrail_id: Optional[str] = None
    llm_provider: Optional[str] = None
    nlp_classifier_id: Optional[str] = None
    default_mode: Optional[str] = None

    def dependencies(self) -> List[str]:
        deps = [self.retrieval_id, self.guardrail_id, self.nlp_classifier_id]
        return list(filter(lambda x: x is not None, deps))


@workflow_router.post("/enterprise-search")
def create_enterprise_search_workflow(
    workflow_name: str,
    options: EnterpriseSearchOptions,
    user: schema.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        validate_name(workflow_name)
    except:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"{workflow_name} is not a valid model name.",
        )

    duplicate_workflow = get_model(
        session, username=user.username, model_name=workflow_name
    )
    if duplicate_workflow:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Workflow with name {workflow_name} already exists for user {user.username}.",
        )

    workflow_id = uuid.uuid4()

    search_model: schema.Model = session.query(schema.Model).get(options.retrieval_id)
    if not search_model:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Search component must be an existing retrieval model. Search model {options.retrieval_id} does not exist.",
        )
    if search_model.type != ModelType.NDB:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Search component must be an existing retrieval model. Search model {options.retrieval_id} is not a retrieval model.",
        )
    if search_model.get_user_permission(user) is None:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"User {user.username} does not have permission to access search model {search_model.name}.",
        )

    if options.guardrail_id:
        guardrail_model = session.query(schema.Model).get(options.guardrail_id)
        if not guardrail_model:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Guardrail component must be an existing nlp model. Guardrail {options.retrieval_id} does not exist.",
            )
        if (
            guardrail_model.type != ModelType.UDT
            or guardrail_model.sub_type != UDTSubType.token
        ):
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Guardrail component must be an existing nlp model. Guardrail {options.retrieval_id} is not a nlp model.",
            )
        if guardrail_model.get_user_permission(user) is None:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"User {user.username} does not have permission to access guardrail model {guardrail_model.name}.",
            )

    try:
        new_workflow = schema.Model(
            id=workflow_id,
            user_id=user.id,
            train_status=schema.Status.complete,
            deploy_status=schema.Status.not_started,
            type=ModelType.ENTERPRISE_SEARCH.value,
            sub_type="",
            name=workflow_name,
            domain=user.domain,
            access_level=schema.Access.private,
            parent_id=None,
        )
        session.add(new_workflow)

        for dep in options.dependencies():
            session.add(schema.ModelDependency(model_id=workflow_id, dependency_id=dep))

        for key, value in options.model_dump().items():
            session.add(
                schema.ModelAttribute(model_id=workflow_id, key=key, value=value)
            )

        session.commit()
    except Exception as err:
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=str(err)
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully created Enterprise Search workflow.",
        data={
            "model_id": str(workflow_id),
            "user_id": str(user.id),
        },
    )
