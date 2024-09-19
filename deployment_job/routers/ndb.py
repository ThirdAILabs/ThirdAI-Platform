import io
import traceback
import uuid
from pathlib import Path
from typing import List, Optional

import fitz
import jwt
import thirdai
from fastapi import APIRouter, Depends, Form, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from file_handler import FileInfo, download_local_files
from permissions import Permissions
from prometheus_client import Summary, Counter
from pydantic import BaseModel, ValidationError
from pydantic_models import inputs
from pydantic_models.inputs import BaseQueryParams, NDBExtraParams
from routers.model import get_model
from update_logger import (
    AssociateLog,
    DeleteLog,
    FeedbackLog,
    ImplicitUpvoteLog,
    InsertLog,
    UpdateLogger,
    UpvoteLog,
)
from utils import propagate_error, response, validate_name
from variables import GeneralVariables

permissions = Permissions()
general_variables = GeneralVariables.load_from_env()

ndb_router = APIRouter()


feedback_logger = UpdateLogger.get_feedback_logger(general_variables.get_data_dir())
insertion_logger = UpdateLogger.get_insertion_logger(general_variables.get_data_dir())
deletion_logger = UpdateLogger.get_deletion_logger(general_variables.get_data_dir())


ndb_query_metric = Summary("ndb_query", "NDB Queries")
ndb_upvote_metric = Summary("ndb_upvote", "NDB upvotes")
ndb_associate_metric = Summary("ndb_associate", "NDB associations")
ndb_implicit_feedback_metric = Summary("ndb_implicit_feedback", "NDB implicit feedback")
ndb_insert_metric = Summary("ndb_insert", "NDB insertions")
ndb_delete_metric = Summary("ndb_delete", "NDB deletions")

ndb_top_k_selections = Counter(
    "ndb_top_k_selections", "Number of top-k results selected by user."
)


@ndb_router.post("/predict")
@ndb_query_metric.time()
@propagate_error
def ndb_query(
    base_params: BaseQueryParams,
    ndb_params: Optional[NDBExtraParams] = NDBExtraParams(),
    _: str = Depends(permissions.verify_permission("read")),
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
    params = base_params.model_dump()
    extra_params = ndb_params.model_dump()
    params.update(extra_params)

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
    write_permission = permissions.check_permission(
        token=token, permission_type="write"
    )

    if not write_permission or general_variables.autoscaling_enabled:
        feedback_logger.log(
            FeedbackLog(
                event=UpvoteLog(
                    chunk_ids=[sample.reference_id for sample in input.text_id_pairs],
                    queries=[sample.query_text for sample in input.text_id_pairs],
                )
            )
        )
        return response(
            status_code=status.HTTP_202_ACCEPTED,
            message="Upvote logged successfully.",
        )
    else:
        model = get_model()
        model.upvote(input.text_id_pairs)

        return response(
            status_code=status.HTTP_200_OK,
            message="Upvote applied successfully.",
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
    write_permission = permissions.check_permission(
        token=token, permission_type="write"
    )

    if not write_permission or general_variables.autoscaling_enabled:
        feedback_logger.log(
            FeedbackLog(
                event=AssociateLog(
                    sources=[sample.source for sample in input.text_pairs],
                    targets=[sample.target for sample in input.text_pairs],
                )
            )
        )
        return response(
            status_code=status.HTTP_202_ACCEPTED,
            message="Associate logged successfully.",
        )
    else:
        model = get_model()
        model.associate(input.text_pairs)

        return response(
            status_code=status.HTTP_200_OK,
            message="Associate applied successfully.",
        )


@ndb_router.post("/implicit-feedback")
@propagate_error
@ndb_implicit_feedback_metric.time()
def implicit_feedback(
    feedback: inputs.ImplicitFeedbackInput,
    _: str = Depends(permissions.verify_permission("read")),
):
    feedback_logger.log(
        FeedbackLog(
            event=ImplicitUpvoteLog(
                chunk_id=feedback.reference_id,
                query=feedback.query_text,
                event_desc=feedback.event_desc,
            )
        )
    )

    if feedback.reference_rank is not None and feedback.reference_rank < 5:
        ndb_top_k_selections.inc()

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

    if general_variables.autoscaling_enabled:
        deletion_logger.log(DeleteLog(doc_ids=input.source_ids))

        return response(
            status_code=status.HTTP_202_ACCEPTED,
            message="Delete logged successfully.",
        )
    else:
        model = get_model()
        model.delete(input.source_ids)

        return response(
            status_code=status.HTTP_200_OK,
            message="Delete applied successfully.",
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


class DocumentList(BaseModel):
    documents: List[FileInfo]


@ndb_router.post("/insert")
@propagate_error
@ndb_insert_metric.time()
def insert(
    documents: str = Form(...),
    files: List[UploadFile] = [],
    _: str = Depends(permissions.verify_permission("write")),
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
        documents = DocumentList.model_validate_json(documents).documents
    except ValidationError as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Invalid format for document insertion.",
            data={"details": str(e), "documents": documents},
        )

    if not documents:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="No documents supplied for insertion. Must supply at least one document.",
        )

    documents = download_local_files(
        files=files,
        file_infos=documents,
        dest_dir=general_variables.get_data_dir() / "insertions" / "documents",
    )

    if general_variables.autoscaling_enabled:
        insertion_logger.log(InsertLog(documents=documents))

        return response(
            status_code=status.HTTP_202_ACCEPTED,
            message="Insert logged successfully.",
        )
    else:
        model = get_model()

        model.insert(documents=documents)

        return response(
            status_code=status.HTTP_200_OK,
            message="Insert applied successfully.",
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
