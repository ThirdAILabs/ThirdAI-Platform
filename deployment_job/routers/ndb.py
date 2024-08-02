import logging
import traceback
import uuid
from typing import List, Optional

import thirdai
from fastapi import APIRouter, Depends, Form, UploadFile, status
from fastapi.encoders import jsonable_encoder
from file_handler import validate_files
from permissions import Permissions
from pydantic import ValidationError
from pydantic_models import inputs
from pydantic_models.documents import DocumentList
from pydantic_models.inputs import BaseQueryParams, NDBExtraParams
from routers.model import get_model, get_token_model
from utils import Status, now, propagate_error, response, validate_name
from variables import GeneralVariables, TypeEnum

permissions = Permissions()
general_variables = GeneralVariables.load_from_env()


def create_ndb_router(task_queue, task_lock, tasks) -> APIRouter:
    """
    Creates an API router for handling NDB-related endpoints.

    Args:
        task_queue (Any): Queue for handling background tasks.
        task_lock (Any): Lock for synchronizing task access.
        tasks (dict): Dictionary to store task details.

    Returns:
        APIRouter: The configured API router.
    """
    ndb_router = APIRouter()

    @ndb_router.post("/predict")
    @propagate_error
    def ndb_query(
        base_params: BaseQueryParams,
        ndb_params: Optional[NDBExtraParams] = NDBExtraParams(),
        token: str = Depends(permissions.verify_read_permission),
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
        if general_variables.type == TypeEnum.NDB:
            extra_params = ndb_params.dict(exclude_unset=True)
            params.update(extra_params)

        params["token"] = token

        results = model.predict(**params)

        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=jsonable_encoder(results),
        )

    @ndb_router.post("/upvote")
    @propagate_error
    def ndb_upvote(
        input: inputs.UpvoteInput,
        token: str = Depends(permissions.verify_write_permission),
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
        model.upvote(text_id_pairs=input.text_id_pairs, token=token)

        return response(status_code=status.HTTP_200_OK, message="Successfully upvoted")

    @ndb_router.post("/associate")
    @propagate_error
    def ndb_associate(
        input: inputs.AssociateInput,
        token: str = Depends(permissions.verify_write_permission),
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
        model.associate(text_pairs=input.text_pairs, token=token)

        return response(
            status_code=status.HTTP_200_OK, message="Successfully associated"
        )

    @ndb_router.get("/sources")
    @propagate_error
    def get_sources(_=Depends(permissions.verify_read_permission)):
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
    def delete(
        input: inputs.DeleteInput,
        token: str = Depends(permissions.verify_write_permission),
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
        model.delete(source_ids=input.source_ids, token=token)

        return response(
            status_code=status.HTTP_200_OK,
            message=f"{len(input.source_ids)} file(s) deleted",
            success=True,
        )

    @ndb_router.post("/save")
    def save(
        input: inputs.SaveModel,
        token: str = Depends(permissions.verify_read_permission),
        override_permission: bool = Depends(permissions.get_owner_permission),
    ):
        """
        Save the current state of the NDB model.

        Parameters:
        - input: SaveModel - The input parameters for saving the model.
        - token: str - Authorization token.
        - override_permission: bool - Whether the user has permission to override the model.

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
                    message="Name must only contain alphanumeric characters, underscores (_), and hyphens (-). ",
                )

            is_model_present = model.reporter.check_model_present(
                token, input.model_name
            )
            if is_model_present:
                return response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="Model name already exists, choose another one.",
                )
        else:
            if not override_permission:
                return response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="You don't have permissions to override this model.",
                )
        try:
            model.save_ndb(model_id=model_id)
            if not input.override:
                model.reporter.save_model(
                    access_token=token,
                    deployment_id=general_variables.deployment_id,
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
    def insert(
        documents: str = Form(...),
        files: List[UploadFile] = [],
        input_mode: str = Form("sync"),
        token: str = Depends(permissions.verify_write_permission),
    ):
        """
        Insert documents into the model.

        Parameters:
        - documents: str - The documents to be inserted in JSON format.
        - files: List[UploadFile] - Optional list of files to be uploaded.
        - input_mode: str - Mode of insertion ("sync" or "async").
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
            "input_mode": "sync"
        }
        ```

        Example Request Body (Async Mode):
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
            "input_mode": "async"
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

        validate_files(documents_list, files, model.data_dir)

        if input_mode == "async":
            task_id = str(uuid.uuid4())
            with task_lock:
                tasks[task_id] = {
                    "status": Status.not_started,
                    "action": "insert",
                    "last_modified": now(),
                    "documents": documents_list,
                    "message": "",
                    "data": None,
                    "token": token,
                }
            task_queue.put((task_id, documents_list))
            return response(
                status_code=status.HTTP_202_ACCEPTED,
                message="Files received, insertion will start soon.",
                data={"task_id": task_id},
            )

        try:
            sources = model.insert(documents=documents_list, token=token)
        except Exception as err:
            logging.error(f"Failed to insert documents: {err}")
            traceback.print_exc()
            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Failed to insert the files",
                success=False,
            )

        return response(
            status_code=status.HTTP_200_OK,
            message=f"{len(sources)} documents uploaded to ndb model",
            data=sources,
            success=True,
        )

    @ndb_router.post("/task-status")
    @propagate_error
    def task_status(
        task_id: str,
        _=Depends(permissions.verify_write_permission),
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
        with task_lock:
            if task_id in tasks:
                return response(
                    status_code=status.HTTP_200_OK,
                    message=f"Information for task {task_id}",
                    data=tasks[task_id],
                )
            else:
                return response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="Task ID not found",
                )

    @ndb_router.post("/pii-detect")
    @propagate_error
    def pii_detection(
        query: str,
        _: str = Depends(permissions.verify_read_permission),
    ):
        token_model = get_token_model()

        results = token_model.predict(query=query, top_k=1)

        return response(
            status_code=status.HTTP_200_OK,
            message="Successfully detected PII.",
            data=jsonable_encoder(results),
        )

    return ndb_router


def process_tasks(task_queue, task_lock, tasks) -> None:
    """
    Processes tasks from the task queue.

    Args:
        task_queue (Any): Queue for handling background tasks.
        task_lock (Any): Lock for synchronizing task access.
        tasks (dict): Dictionary to store task details.
    """
    model = get_model()
    while True:
        task_id, documents = task_queue.get()
        try:
            with task_lock:
                tasks[task_id]["status"] = Status.in_progress
                tasks[task_id]["last_modified"] = now()

            sources = model.insert(documents=documents, token=tasks[task_id]["token"])

            with task_lock:
                tasks[task_id]["status"] = Status.complete
                tasks[task_id]["data"] = sources
                tasks[task_id]["last_modified"] = now()

        except Exception as e:
            with task_lock:
                tasks[task_id]["status"] = Status.failed
                tasks[task_id]["message"] = str(traceback.format_exc())
                tasks[task_id]["last_modified"] = now()
                logging.error(
                    f"Task {task_id} with data {tasks[task_id]} failed: {str(traceback.format_exc())}"
                )
