from typing import Optional

from backend.utils import response
from database import schema
import uuid
from database.session import get_session
from backend.auth_dependencies import get_current_user
from fastapi import APIRouter, Depends, status
from backend.deployment_config import ModelType
from sqlalchemy.orm import Session
from backend.utils import validate_name, get_model
from pydantic import BaseModel

workflow_router = APIRouter()


class RagDefinition(BaseModel):
    search_id: str
    guardrail_id: Optional[str] = None
    sentiment_id: Optional[str] = None

    genai_provider: Optional[str] = None


@workflow_router.post("/rag")
def create_rag_workflow(
    workflow_name: str,
    definition: RagDefinition,
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

    workflow_id = uuid.uui4()

    try:
        new_workflow = schema.Model(
            id=workflow_id,
            user_id=user.id,
            train_status=schema.Status.complete,
            deploy_status=schema.Status.not_started,
            type=ModelType.RAG.value,
            sub_type="",
            name=workflow_name,
            domain=user.domain,
            access_level=schema.Access.private,
            parent_id=None,
            definition=definition.model_dump_json(),
        )
        session.add(new_workflow)
        session.commit()
        session.refresh(new_workflow)
    except Exception as err:
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=str(err)
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully created RAG workflow.",
        data={
            "model_id": str(workflow_id),
            "user_id": str(user.id),
        },
    )
