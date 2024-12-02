import os
import pathlib
import uuid
from typing import List, Optional

from auth.jwt import AuthenticatedUser, verify_access_token
from backend.auth_dependencies import get_current_user
from backend.utils import get_model, validate_name
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from platform_common.dependencies import is_on_low_disk
from platform_common.knowledge_extraction.schema import (
    Keyword,
    Question,
    get_knowledge_db_session,
)
from platform_common.pydantic_models.training import (
    ModelType,
    QuestionKeywords,
    UDTSubType,
)
from platform_common.utils import disk_usage, get_section, model_bazaar_path, response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

workflow_router = APIRouter()

root_folder = pathlib.Path(__file__).parent

docs_file = root_folder.joinpath("../../docs/workflow_endpoints.txt")

with open(docs_file) as f:
    docs = f.read()


class EnterpriseSearchOptions(BaseModel):
    retrieval_id: str
    guardrail_id: Optional[str] = None
    llm_provider: Optional[str] = None
    nlp_classifier_id: Optional[str] = None
    default_mode: Optional[str] = None

    def dependencies(self) -> List[str]:
        deps = [self.retrieval_id, self.guardrail_id, self.nlp_classifier_id]
        return list(filter(lambda x: x is not None, deps))


@workflow_router.post(
    "/enterprise-search",
    dependencies=[Depends(is_on_low_disk())],
    summary="Create Enterprise Search Workflow",
    description=get_section(docs, "Create Enterprise Search Workflow"),
)
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
            "disk_usage": disk_usage(),
        },
    )


class KnowledgeExtractionRequest(BaseModel):
    model_name: str = Field(..., description="The name of the model to be created.")
    questions: List[QuestionKeywords] = Field(
        ..., description="A list of questions with optional keywords.", min_length=1
    )
    llm_provider: str

    advanced_indexing: bool = True
    rerank: bool = True
    generate_answers: bool = True

    @model_validator(mode="after")
    def check_valid_llm_provider(self):
        if self.llm_provider not in {"on-prem", "openai", "cohere"}:
            raise ValueError("Invalid llm_provider specified.")
        return self


@workflow_router.post("/knowledge-extraction", dependencies=[Depends(is_on_low_disk())])
def train_knowledge_extraction(
    request: KnowledgeExtractionRequest,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    user: schema.User = authenticated_user.user

    try:
        validate_name(request.model_name)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{request.model_name}' is not a valid model name.",
        )

    unique_questions = set()
    for q in request.questions:
        question = q.question.lower()
        if question in unique_questions:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Duplicate question '{q.question}' detected",
            )
        unique_questions.add(question)

    duplicate_model = get_model(
        session, username=user.username, model_name=request.model_name
    )
    if duplicate_model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model with name '{request.model_name}' already exists for user '{user.username}'.",
        )

    try:
        new_model = schema.Model(
            user_id=user.id,
            train_status=schema.Status.not_started,
            deploy_status=schema.Status.not_started,
            name=request.model_name,
            type=ModelType.KNOWLEDGE_EXTRACTION,
            domain=user.domain,
            access_level=schema.Access.private,
        )
        session.add(new_model)
        session.commit()
        session.refresh(new_model)
        attributes = {
            "llm_provider": request.llm_provider,
            "advanced_indexing": request.advanced_indexing,
            "rerank": request.rerank,
            "generate_answers": request.generate_answers,
        }
        for k, v in attributes.items():
            session.add(schema.ModelAttribute(model_id=new_model.id, key=k, value=v))
        session.commit()

    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create the model: {err}",
        )

    new_model.train_status = schema.Status.in_progress
    session.commit()

    knowledge_db_path = os.path.join(
        model_bazaar_path(), "models", str(new_model.id), "knowledge.db"
    )
    os.makedirs(os.path.dirname(knowledge_db_path), exist_ok=True)

    try:
        KnowledgeSessionLocal = get_knowledge_db_session(knowledge_db_path)
        knowledge_session = KnowledgeSessionLocal()
        # Save questions and keywords in the knowledge extraction database
        for question_item in request.questions:
            question = Question(
                id=str(uuid.uuid4()), question_text=question_item.question
            )
            knowledge_session.add(question)
            if question_item.keywords:
                for keyword in question_item.keywords:
                    keyword_entry = Keyword(
                        id=str(uuid.uuid4()), question_id=question.id, text=keyword
                    )
                    knowledge_session.add(keyword_entry)
        knowledge_session.commit()
    except Exception as err:
        knowledge_session.rollback()
        new_model.train_status = schema.Status.failed
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store questions and keywords: {err}",
        )
    finally:
        knowledge_session.close()

    new_model.train_status = schema.Status.complete
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully created the knowledge extraction model.",
        data={"model_id": str(new_model.id), "user_id": str(user.id)},
    )
