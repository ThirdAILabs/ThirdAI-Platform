import io
import json
import traceback
import uuid
from pathlib import Path
from typing import List, Optional

import fitz
import jwt
import thirdai
from fastapi import APIRouter, Depends, Form, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from feedback_logger import AssociateLog, FeedbackLog, ImplicitUpvoteLog, UpvoteLog
from file_handler import validate_files
from permissions import Permissions
from prometheus_client import Summary
from pydantic import ValidationError, parse_obj_as
from pydantic_models import inputs
from pydantic_models.documents import DocumentList
from pydantic_models.inputs import (
    AssociateInputSingle,
    BaseQueryParams,
    NDBExtraParams,
    UpvoteInputSingle,
)
from routers.model import get_model
from utils import Status, now, propagate_error, response, validate_name
from variables import GeneralVariables

permissions = Permissions()
general_variables = GeneralVariables.load_from_env()

ndb_router = APIRouter()


ndb_query_metric = Summary("ndb_query", "NDB Queries")
ndb_upvote_metric = Summary("ndb_upvote", "NDB upvotes")
ndb_associate_metric = Summary("ndb_associate", "NDB associations")
ndb_implicit_feedback_metric = Summary("ndb_implicit_feedback", "NDB implicit feedback")
ndb_insert_metric = Summary("ndb_insert", "NDB insertions")
ndb_delete_metric = Summary("ndb_delete", "NDB deletions")


@ndb_router.post("/predict")
@ndb_query_metric.time()
@propagate_error
def ndb_query(
    base_params: BaseQueryParams,
    ndb_params: Optional[NDBExtraParams] = NDBExtraParams(),
    token: str = Depends(permissions.verify_permission("read")),
):
    """
    Query the NDB model with specified parameters.

    Parameters:
    - base_params: BaseQueryParams - Basic query parameters.
        - query: str - The query text.
        - top_k: int - The number of top results to return (default: 5).
    - ndb_params: Optional[NDBExtraParams] - Extra NDB-specific query parameters.
        - rerank: bool - Whether to rerank the results (default: False).
        - top_k_rerank: int - The number of top results to rerank (default: 100).
        - context_radius: int - The context radius for the results (default: 1).
        - rerank_threshold: float - The threshold for reranking (default: 1.5).
        - top_k_threshold: Optional[int] - The threshold for top_k results.
        - constraints: Constraints - Additional constraints for the query.
    - token: str - Authorization token.

    Returns:
    - JSONResponse: The query results.

    Example Request Body:
    ```
    {
        "base_params": {
            "query": "What is the capital of France?",
            "top_k": 5
        },
        "ndb_params": {
            "rerank": true,
            "top_k_rerank": 100,
            "context_radius": 1,
            "rerank_threshold": 1.5,
            "constraints": {
                "field1": {
                    "constraint_type": "AnyOf",
                    "values": ["value1", "value2"]
                },
                "field2": {
                    "constraint_type": "InRange",
                    "minimum": 0,
                    "maximum": 10,
                    "inclusive_min": true,
                    "inclusive_max": true
                }
            }
        }
    }
    ```
    """
    model = get_model()
    params = base_params.dict()
    extra_params = ndb_params.dict(exclude_unset=True)
    params.update(extra_params)

    params["token"] = token

    results = model.predict(**params)

    return response(
        status_code=status.HTTP_200_OK,
        message="Successful",
        data=jsonable_encoder(results),
    )


@ndb_router.post("/update-chat-settings")
@propagate_error
def update_chat_settings(
    settings: inputs.ChatSettings,
    _=Depends(permissions.verify_permission("write")),
):
    model = get_model()

    model.set_chat(**(settings.dict()))

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully updated chat settings",
    )


@ndb_router.post("/get-chat-history")
@propagate_error
def get_chat_history(
    input: inputs.ChatHistoryInput,
    token=Depends(permissions.verify_permission("read")),
):
    model = get_model()
    if not model.chat:
        raise Exception(
            "Chat is not enabled. Please provide an GenAI key to enable chat."
        )

    if not input.session_id:
        try:
            # Use logged-in user id as the chat session id if no other session id is provided
            session_id = jwt.decode(token, options={"verify_signature": False})[
                "user_id"
            ]
        except:
            raise Exception(
                "Must provide a session ID or be logged in to use chat feature"
            )
    else:
        session_id = input.session_id

    chat_history = {"chat_history": model.chat.get_chat_history(session_id)}

    return response(
        status_code=status.HTTP_200_OK,
        message="Successful",
        data=chat_history,
    )


@ndb_router.post("/chat")
@propagate_error
def chat(input: inputs.ChatInput, token=Depends(permissions.verify_permission("read"))):
    model = get_model()
    if not model.chat:
        raise Exception(
            "Chat is not enabled. Please provide an GENAI key to enable chat."
        )

    if not input.session_id:
        try:
            # Use logged-in user id as the chat session id if no other session id is provided
            session_id = jwt.decode(token, options={"verify_signature": False})[
                "user_id"
            ]
        except:
            raise Exception(
                "Must provide a session ID or be logged in to use chat feature"
            )
    else:
        session_id = input.session_id

    chat_result = {"response": model.chat.chat(input.user_input, session_id)}

    return response(
        status_code=status.HTTP_200_OK,
        message="Successful",
        data=chat_result,
    )


@ndb_router.post("/upvote")
@propagate_error
@ndb_upvote_metric.time()
def ndb_upvote(
    input: inputs.UpvoteInput,
    token: str = Depends(permissions.verify_permission("read")),
):
    """
    Upvote specific text-id pairs.

    Parameters:
    - input: UpvoteInput - The upvote input containing text-id pairs.
    - token: str - Authorization token.

    Returns:
    - JSONResponse: Upvote success message.

    Example Request Body:
    ```
    {
        "text_id_pairs": [
            {"query_text": "What is AI?", "reference_id": 1},
            {"query_text": "What is machine learning?", "reference_id": 2}
        ]
    }
    ```
    """
    model = get_model()

    write_permission = model.permissions.check_permission(
        token=token, permission_type="write"
    )

    if not write_permission:
        model.feedback_logger.log(
            FeedbackLog(
                event=UpvoteLog(
                    chunk_ids=[sample.reference_id for sample in input.text_id_pairs],
                    queries=[sample.query_text for sample in input.text_id_pairs],
                )
            )
        )
    else:
        task_id = str(uuid.uuid4())
        task_data = {
            "task_id": task_id,
            "model_id": general_variables.model_id,
            "action": "upvote",
            "text_id_pairs": json.dumps(jsonable_encoder(input.text_id_pairs)),
            "token": token,
            "status": Status.not_started,
            "last_modified": now(),
            "message": "",
        }

        model.redis_publish(task_id=task_id, task_data=task_data)

        return response(
            status_code=status.HTTP_202_ACCEPTED,
            message="Upvote task queued successfully.",
            data={"task_id": task_id},
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Upvote task logged successfully.",
    )


@ndb_router.post("/associate")
@propagate_error
@ndb_associate_metric.time()
def ndb_associate(
    input: inputs.AssociateInput,
    token: str = Depends(permissions.verify_permission("read")),
):
    """
    Associate text pairs in the model.

    Parameters:
    - input: AssociateInput - The associate input containing text pairs.
    - token: str - Authorization token.

    Returns:
    - JSONResponse: Association success message.

    Example Request Body:
    ```
    {
        "text_pairs": [
            {"source": "AI", "target": "Artificial Intelligence"},
            {"source": "ML", "target": "Machine Learning"}
        ]
    }
    ```
    """
    model = get_model()
    write_permission = model.permissions.check_permission(
        token=token, permission_type="write"
    )

    if not write_permission:
        model.feedback_logger.log(
            FeedbackLog(
                event=AssociateLog(
                    sources=[sample.source for sample in input.text_pairs],
                    targets=[sample.target for sample in input.text_pairs],
                )
            )
        )
    else:
        task_id = str(uuid.uuid4())
        task_data = {
            "task_id": task_id,
            "model_id": general_variables.model_id,
            "action": "associate",
            "text_pairs": json.dumps(jsonable_encoder(input.text_pairs)),
            "token": token,
            "status": Status.not_started,
            "last_modified": now(),
            "message": "",
        }

        model.redis_publish(task_id=task_id, task_data=task_data)

        return response(
            status_code=status.HTTP_202_ACCEPTED,
            message="Associate task queued successfully.",
            data={"task_id": task_id},
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Associate task logged successfully.",
    )


@ndb_router.post("/implicit-feedback")
@propagate_error
@ndb_implicit_feedback_metric.time()
def implicit_feedback(
    feedback: inputs.ImplicitFeedbackInput,
    _: str = Depends(permissions.verify_permission("read")),
):
    model = get_model()
    model.feedback_logger.log(
        FeedbackLog(
            event=ImplicitUpvoteLog(
                chunk_id=feedback.reference_id,
                query=feedback.query_text,
                event_desc=feedback.event_desc,
            )
        )
    )

    return response(
        status_code=status.HTTP_200_OK,
        message="Implicit feedback logged successfully.",
    )


@ndb_router.get("/sources")
@propagate_error
def get_sources(_=Depends(permissions.verify_permission("read"))):
    """
    Get the sources used in the model.

    Parameters:
    - token: str - Authorization token.

    Returns:
    - JSONResponse: The list of sources.

    Example Response Body:
    ```
    {
        "status": "success",
        "message": "Successful",
        "data": ["source1", "source2", "source3"]
    }
    ```
    """
    model = get_model()
    sources = model.sources()
    return response(
        status_code=status.HTTP_200_OK,
        message="Successful",
        data=sources,
    )


@ndb_router.post("/delete")
@propagate_error
@ndb_delete_metric.time()
def delete(
    input: inputs.DeleteInput,
    token: str = Depends(permissions.verify_permission("write")),
):
    """
    Delete sources from the model.

    Parameters:
    - input: DeleteInput - The input containing source IDs to be deleted.
    - token: str - Authorization token.

    Returns:
    - JSONResponse: Deletion success message.

    Example Request Body:
    ```
    {
        "source_ids": ["source1", "source2"]
    }
    ```
    """
    model = get_model()
    task_id = str(uuid.uuid4())
    task_data = {
        "task_id": task_id,
        "model_id": general_variables.model_id,
        "action": "delete",
        "source_ids": json.dumps(jsonable_encoder(input.source_ids)),
        "token": token,
        "status": Status.not_started,
        "last_modified": now(),
        "message": "",
    }

    model.redis_publish(task_id=task_id, task_data=task_data)

    return response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Delete task queued successfully.",
        data={"task_id": task_id},
    )


@ndb_router.post("/save")
def save(
    input: inputs.SaveModel,
    token: str = Depends(permissions.verify_permission("read")),
):
    """
    Save the current state of the NDB model.

    Parameters:
    - input: SaveModel - The input parameters for saving the model.
    - token: str - Authorization token.

    Returns:
    - JSONResponse: Save success message.

    Example Request Body:
    ```
    {
        "override": false,
        "model_name": "new_model_name"
    }
    ```
    """
    model = get_model()
    model_id = general_variables.model_id
    if not input.override:
        model_id = str(uuid.uuid4())
        if not input.model_name:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Model name is required for new model.",
            )

        try:
            validate_name(input.model_name)
        except Exception:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Name must only contain alphanumeric characters, underscores (_), and hyphens (-).",
            )

        is_model_present = model.reporter.check_model_present(token, input.model_name)
        if is_model_present:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Model name already exists, choose another one.",
            )
    else:
        override_permission = permissions.check_permission(
            token=token, permission_type="override"
        )
        if not override_permission:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="You don't have permissions to override this model.",
            )
    try:
        model.save(model_id=model_id)
        if not input.override:
            model.reporter.save_model(
                access_token=token,
                model_id=model_id,
                base_model_id=general_variables.model_id,
                model_name=input.model_name,
                metadata={"thirdai_version": str(thirdai.__version__)},
            )
    except Exception as err:
        traceback.print_exc()
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=str(err)
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully saved the model.",
        data={"new_model_id": model_id if not input.override else None},
    )


@ndb_router.post("/insert")
@propagate_error
@ndb_insert_metric.time()
def insert(
    documents: str = Form(...),
    files: List[UploadFile] = [],
    token: str = Depends(permissions.verify_permission("write")),
):
    """
    Insert documents into the model.

    Parameters:
    - documents: str - The documents to be inserted in JSON format.
    - files: List[UploadFile] - Optional list of files to be uploaded.
    - token: str - Authorization token.

    Returns:
    - JSONResponse: Insertion success message.

    Example Request Body (Sync Mode):
    ```
    {
        "documents": [
            {
                "location": "local",
                "document_type": "PDF",
                "path": "/path/to/file.pdf",
                "metadata": {"author": "John Doe"},
                "chunk_size": 100,
                "stride": 40,
                "emphasize_first_words": 0,
                "ignore_header_footer": true,
                "ignore_nonstandard_orientation": true
            }
        ],
    }
    ```
    """
    try:
        documents_list = DocumentList.model_validate_json(documents).model_dump()
    except ValidationError as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Invalid format for document insertion.",
            data={"details": str(e), "documents": documents},
        )

    if not documents_list:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="No documents supplied for insertion. Must supply at least one document.",
        )

    model = get_model()

    # TODO(YASH): Handle multiple files with same name across multiple calls or single
    # call, one way is to append task_id along with data_dir.
    validate_files(documents_list, files, model.data_dir)

    task_id = str(uuid.uuid4())
    task_data = {
        "task_id": task_id,
        "model_id": general_variables.model_id,
        "action": "insert",
        "documents": json.dumps(documents_list),
        "token": token,
        "status": Status.not_started,
        "last_modified": now(),
        "message": "",
    }

    model.redis_publish(task_id=task_id, task_data=task_data)

    return response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Insert task queued successfully.",
        data={"task_id": task_id},
    )


@ndb_router.post("/task-status")
@propagate_error
def task_status(
    task_id: str,
    _=Depends(permissions.verify_permission("write")),
):
    """
    Get the status of a specific task.

    Parameters:
    - task_id: str - The ID of the task.

    Returns:
    - JSONResponse: The status of the task.

    Example Request Body:
    ```
    {
        "task_id": "1234-5678-91011-1213"
    }
    ```

    Example Response Body:
    ```
    {
        "status": "success",
        "message": "Information for task 1234-5678-91011-1213",
        "data": {
            "status": "in_progress",
            "action": "insert",
            "last_modified": "2024-07-31T12:34:56.789Z",
            "documents": [...],
            "message": "",
            "data": null,
            "token": "token_value"
        }
    }
    ```
    """
    model = get_model()
    task_data = model.redis_client.hgetall(f"task:{task_id}")
    if task_data:
        return response(
            status_code=status.HTTP_200_OK,
            message=f"Information for task {task_id}",
            data=jsonable_encoder(task_data),
        )
    else:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Task ID not found",
        )


@ndb_router.get("/highlighted-pdf")
@propagate_error
def highlighted_pdf(
    reference_id: int, _=Depends(permissions.verify_permission("read"))
):
    """
    Get a highlighted PDF based on the reference ID.

    Parameters:
    - reference_id: int - The reference ID of the document.

    Returns:
    - Response: The highlighted PDF as a stream.

    Example Request:
    ```
    /highlighted-pdf?reference_id=123
    ```
    """
    model = get_model()
    source, pdf_bytes = model.highlight_pdf(reference_id)
    buffer = io.BytesIO(pdf_bytes)
    headers = {"Content-Disposition": f'inline; filename="{Path(source).name}"'}
    return Response(buffer.getvalue(), headers=headers, media_type="application/pdf")


@ndb_router.get("/pdf-blob")
@propagate_error
def pdf_blob(source: str, _=Depends(permissions.verify_permission("read"))):
    """
    Get the PDF blob from the source.

    Parameters:
    - source: str - The source path of the PDF.

    Returns:
    - Response: The PDF as a stream.

    Example Request:
    ```
    /pdf-blob?source=/path/to/pdf
    ```
    """
    buffer = io.BytesIO(fitz.open(source).tobytes())
    headers = {"Content-Disposition": f'inline; filename="{Path(source).name}"'}
    return Response(buffer.getvalue(), headers=headers, media_type="application/pdf")


@ndb_router.get("/pdf-chunks")
@propagate_error
def pdf_chunks(reference_id: int, _=Depends(permissions.verify_permission("read"))):
    """
    Get the chunks of a PDF document based on the reference ID.

    Parameters:
    - reference_id: int - The reference ID of the document.

    Returns:
    - JSONResponse: The chunks of the PDF document.

    Example Request:
    ```
    /pdf-chunks?reference_id=123
    ```
    """
    model = get_model()
    if chunks := model.chunks(reference_id):
        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=chunks,
        )
    return response(
        status_code=status.HTTP_400_BAD_REQUEST,
        message=f"Reference with id ${reference_id} is not a PDF.",
        data={},
    )


def process_ndb_task(task):
    """
    Process a single task based on the task action.

    Args:
        task (dict): The task data fetched from Redis.
    """
    model = get_model(write_mode=True)
    task_id = task.get("task_id")
    try:
        # Update task status to "in_progress"
        task["status"] = Status.in_progress  # Use the enum value for status
        task["last_modified"] = now()  # Convert datetime to string
        model.redis_client.hset(
            f"task:{task_id}",
            mapping={
                k: json.dumps(v) if isinstance(v, (list, dict)) else v
                for k, v in task.items()
            },
        )

        action = task.get("action")
        model_id = task.get("model_id")

        if action == "upvote":
            # Deserialize and load back into Pydantic model
            text_id_pairs = parse_obj_as(
                List[UpvoteInputSingle], task.get("text_id_pairs", "[]")
            )
            model.upvote(text_id_pairs=text_id_pairs, token=task.get("token"))
            model.logger.info(
                f"Successfully upvoted for model_id: {model_id}, task_id: {task_id} and task_data: {task}"
            )

        elif action == "associate":
            # Deserialize and load back into Pydantic model
            text_pairs = parse_obj_as(
                List[AssociateInputSingle], task.get("text_pairs", "[]")
            )
            model.associate(text_pairs=text_pairs, token=task.get("token"))
            model.logger.info(
                f"Successfully associated text pairs for model_id: {model_id}, task_id: {task_id} and task_data: {task}"
            )

        elif action == "delete":
            # Deserialize and load back into Pydantic model
            source_ids = task.get("source_ids", "[]")
            model.delete(source_ids=source_ids, token=task.get("token"))
            model.logger.info(
                f"Successfully deleted sources for model_id: {model_id}, task_id: {task_id} and task_data: {task}"
            )

        elif action == "insert":
            documents = task.get("documents", "[]")  # Decode JSON
            model.insert(documents=documents, token=task.get("token"))
            model.logger.info(
                f"Successfully inserted documents for model_id: {model_id}, task_id: {task_id} and task_data: {task}"
            )

        # Mark task as completed
        task["status"] = Status.complete
        task["last_modified"] = now()
        model.redis_client.hset(
            f"task:{task_id}",
            mapping={
                k: json.dumps(v) if isinstance(v, (list, dict)) else v
                for k, v in task.items()
            },
        )
        model.logger.info(
            f"Successfully updated the status of the task {task_id} to complete"
        )

    except Exception as e:
        model.logger.error(f"Failed to process task {task_id}: {str(e)}")
        traceback.print_exc()
        # Update task status to "failed" and log the error
        task["status"] = Status.failed
        task["last_modified"] = now()
        task["message"] = str(e)
        model.redis_client.hset(
            f"task:{task_id}",
            mapping={
                k: json.dumps(v) if isinstance(v, (list, dict)) else v
                for k, v in task.items()
            },
        )
    finally:
        model.redis_client.srem(f"tasks_by_model:{model_id}", task_id)
        model.redis_client.delete(f"task:{task_id}")
        model.logger.info(f"Task {task_id} removed from Redis.")
