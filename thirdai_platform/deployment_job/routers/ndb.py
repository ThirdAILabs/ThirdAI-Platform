import io
import threading
import traceback
import uuid
from pathlib import Path
from queue import Queue
from typing import AsyncGenerator, List, Optional

import fitz
import jwt
import thirdai
from deployment_job.models.ndb_models import NDBModel
from deployment_job.permissions import Permissions
from deployment_job.pydantic_models.inputs import (
    AssociateInput,
    ChatHistoryInput,
    ChatInput,
    ChatSettings,
    DeleteInput,
    DocumentList,
    ImplicitFeedbackInput,
    NDBSearchParams,
    SaveModel,
    UpvoteInput,
)
from deployment_job.reporter import Reporter
from deployment_job.update_logger import UpdateLogger
from deployment_job.utils import Task, TaskAction, TaskStatus, now, validate_name
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    Response,
    UploadFile,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from platform_common.dependencies import is_on_low_disk
from platform_common.file_handler import download_local_files, get_cloud_client
from platform_common.logging import LogCode
from platform_common.logging.job_loggers import JobLogger
from platform_common.pydantic_models.deployment import DeploymentConfig
from platform_common.pydantic_models.feedback_logs import (
    AssociateLog,
    DeleteLog,
    FeedbackLog,
    ImplicitUpvoteLog,
    InsertLog,
    UpvoteLog,
)
from platform_common.utils import response
from prometheus_client import Counter, Summary
from pydantic import ValidationError

ndb_query_metric = Summary("ndb_query", "NDB Queries")
ndb_upvote_metric = Summary("ndb_upvote", "NDB upvotes")
ndb_associate_metric = Summary("ndb_associate", "NDB associations")
ndb_implicit_feedback_metric = Summary("ndb_implicit_feedback", "NDB implicit feedback")
ndb_insert_metric = Summary("ndb_insert", "NDB insertions")
ndb_delete_metric = Summary("ndb_delete", "NDB deletions")

TOPK_SELECTIONS_TO_TRACK = 5
ndb_top_k_selections = [
    Counter(
        f"ndb_result_{i}_selections", f"Number of selections of result {i} by user."
    )
    for i in range(1, 1 + TOPK_SELECTIONS_TO_TRACK)
]


class NDBRouter:
    def __init__(self, config: DeploymentConfig, reporter: Reporter, logger: JobLogger):
        self.config = config
        self.reporter = reporter
        self.logger = logger

        self.model: NDBModel = NDBRouter.get_model(config, logger)

        self.feedback_logger = UpdateLogger.get_feedback_logger(self.model.data_dir)
        self.insertion_logger = UpdateLogger.get_insertion_logger(self.model.data_dir)
        self.deletion_logger = UpdateLogger.get_deletion_logger(self.model.data_dir)

        self.router = APIRouter()
        self.router.add_api_route("/search", self.search, methods=["POST"])
        self.router.add_api_route(
            "/insert",
            self.insert,
            methods=["POST"],
            dependencies=[Depends(is_on_low_disk(path=self.config.model_bazaar_dir))],
        )
        self.router.add_api_route("/delete", self.delete, methods=["POST"])
        self.router.add_api_route("/tasks", self.get_tasks, methods=["GET"])
        self.router.add_api_route("/upvote", self.upvote, methods=["POST"])
        self.router.add_api_route("/associate", self.associate, methods=["POST"])
        self.router.add_api_route(
            "/implicit-feedback", self.implicit_feedback, methods=["POST"]
        )
        self.router.add_api_route(
            "/update-chat-settings", self.update_chat_settings, methods=["POST"]
        )
        self.router.add_api_route(
            "/get-chat-history", self.get_chat_history, methods=["POST"]
        )
        self.router.add_api_route("/chat", self.chat, methods=["POST"])
        self.router.add_api_route("/sources", self.get_sources, methods=["GET"])
        self.router.add_api_route(
            "/save",
            self.save,
            methods=["POST"],
            dependencies=[Depends(is_on_low_disk(path=self.config.model_bazaar_dir))],
        )
        self.router.add_api_route(
            "/highlighted-pdf", self.highlighted_pdf, methods=["GET"]
        )
        self.router.add_api_route("/pdf-blob", self.pdf_blob, methods=["GET"])
        self.router.add_api_route("/pdf-chunks", self.pdf_chunks, methods=["GET"])
        self.router.add_api_route(
            "/get-signed-url", self.get_signed_url, methods=["GET"]
        )

        # Only enable task queue in dev mode
        if not self.config.autoscaling_enabled:
            self.task_queue = Queue()
            # TODO(kartik): make tasks an on-disk data structure
            self.tasks = {}
            self.task_lock = threading.Lock()

        threading.Thread(target=self.process_tasks, daemon=True).start()

    @staticmethod
    def get_model(config: DeploymentConfig, logger: JobLogger) -> NDBModel:
        return NDBModel(
            config=config, logger=logger, write_mode=not config.autoscaling_enabled
        )

    @ndb_query_metric.time()
    def search(
        self,
        params: NDBSearchParams,
        token: str = Depends(Permissions.verify_permission("read")),
    ):
        """
        Query the NDB model with specified parameters.

        Parameters:
        - query: str - The query text.
        - top_k: int - The number of top results to return (default: 5).
        - constraints: Constraints - Additional constraints for the query.
        - rerank: bool - Whether to rerank the results (default: False).
        - context_radius: int - The context radius for the results (default: 1).
        - token: str - Authorization token.

        Returns:
        - JSONResponse: The query results.

        Example Request Body:
        ```
        {
            "query": "What is the capital of France?",
            "top_k": 5
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
        ```
        """
        results = self.model.predict(**params.model_dump())

        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=jsonable_encoder(results),
        )

    @ndb_insert_metric.time()
    def insert(
        self,
        documents: str = Form(...),
        files: List[UploadFile] = [],
        sync: bool = True,
        token: str = Depends(Permissions.verify_permission("write")),
    ):
        """
        Insert documents into the model.

        Parameters:
        - documents: str - The documents to be inserted in JSON format.
            - path: str - Path of the file.
            - location: str - Where the file is stored. If uploading a file, this will be "local". Other options include "nfs", "s3", "gcp", "azure".
            - source_id: Optional[str] - A user specified source id for the uploaded document. If not provided, a random source_id will be created.
            - options: Dict[str, Any] - Custom options for this inserted doc. (default: {})
                - {"upsert": True} can only be used if source_id is specified. The newly uploaded document will replace the document that currently has source_id.
            - metadata: Optional[Dict[str, Any]] - Metadata to assign to this doc. Can be used to filter documents.
        - files: List[UploadFile] - Optional list of files to be uploaded.
        - sync: bool - Whether to sychronously insert docs or queue insertion and return asynchronously (default: True)
        - token: str - Authorization token.

        Returns:
        - JSONResponse: Insertion success message.

        Example Documents Param Request Body:
        ```
        {
            "documents": [
                {
                    "location": "local",
                    "path": "/path/to/file.pdf",
                    "metadata": {"author": "John Doe"},
                    "options": {"upsert": True},
                    "source_id": "1234",
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

        total_filesize = sum(file.size or 0 for file in files)

        if self.config.autoscaling_enabled:
            max_filesize_mb = 200
        else:
            max_filesize_mb = 50

        if total_filesize > (max_filesize_mb * 1024 * 1024):
            message = f"Size of uploaded files exceeds maximum of {max_filesize_mb}Mb for insertion endpoint on active deployment. Please use retraining api for updates of this size."
            self.logger.error(message, code=LogCode.FILE_VALIDATION)
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=message,
            )

        documents = download_local_files(
            files=files,
            file_infos=documents,
            dest_dir=self.model.data_dir / "insertions" / "documents",
        )

        if self.config.autoscaling_enabled:
            self.insertion_logger.log(InsertLog(documents=documents))
            self.logger.info(
                "Document insertion logged for autoscaling deployment",
                code=LogCode.MODEL_INSERT,
            )
            return response(
                status_code=status.HTTP_202_ACCEPTED,
                message="Insert logged successfully.",
            )
        elif not sync:
            task_id = str(uuid.uuid4())
            with self.task_lock:
                self.task_queue.put(task_id)
                self.tasks[task_id] = Task(
                    status=TaskStatus.NOT_STARTED,
                    action=TaskAction.INSERT,
                    last_modified=now(),
                    data={"documents": documents},
                )

            self.logger.info("Document insertion queued")
            return response(
                status_code=status.HTTP_202_ACCEPTED,
                message=f"Files received, insertion will start soon.",
                data={"task_id": task_id},
            )
        else:
            try:
                inserted_docs = self.model.insert(documents=documents)
                self.logger.info(
                    "Document insertion applied successfully", code=LogCode.MODEL_INSERT
                )
                return response(
                    status_code=status.HTTP_200_OK,
                    message="Insert applied successfully.",
                    data=inserted_docs,
                )
            except Exception as e:
                self.logger.error(
                    f"Error inserting documents: {e}", code=LogCode.MODEL_INSERT
                )
                return response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Error inserting documents",
                )

    @ndb_delete_metric.time()
    def delete(
        self,
        input: DeleteInput,
        sync: bool = True,
        token: str = Depends(Permissions.verify_permission("write")),
    ):
        """
        Delete sources from the model.

        Parameters:
        - input: DeleteInput - The input containing source IDs to be deleted.
        - sync: bool - Whether to sychronously delete docs or queue deletion and return asynchronously (default: False)
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

        if self.config.autoscaling_enabled:
            self.deletion_logger.log(DeleteLog(doc_ids=input.source_ids))
            self.logger.info(
                "Deletion logged for autoscaling deployment", code=LogCode.MODEL_DELETE
            )
            return response(
                status_code=status.HTTP_202_ACCEPTED,
                message="Delete logged successfully.",
            )
        elif not sync:
            task_id = str(uuid.uuid4())
            with self.task_lock:
                self.task_queue.put(task_id)
                self.tasks[task_id] = Task(
                    status=TaskStatus.NOT_STARTED,
                    action=TaskAction.DELETE,
                    last_modified=now(),
                    data={"source_ids": input.source_ids},
                )
            self.logger.info("Deletion queued")
            return response(
                status_code=status.HTTP_202_ACCEPTED,
                message=f"Source ids received, deletion will start soon.",
                data={"task_id": task_id},
            )
        else:
            if len(input.source_ids) > 5:
                message = f"Number of deletions exceeds the maximum {input.source_ids} that can be processed synchronously in an active deployment."
                self.logger.error(message, code=LogCode.MODEL_DELETE)
                return response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message=message,
                )
            try:
                self.model.delete(input.source_ids)
                self.logger.info(
                    "Document deletion applied successfully", code=LogCode.MODEL_DELETE
                )
                return response(
                    status_code=status.HTTP_200_OK,
                    message="Delete applied successfully.",
                )
            except Exception as e:
                self.logger.error(
                    f"Error deleting documents: {e}", code=LogCode.MODEL_DELETE
                )
                return response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Error deleting documents",
                )

    @ndb_upvote_metric.time()
    def upvote(
        self,
        input: UpvoteInput,
        token: str = Depends(Permissions.verify_permission("read")),
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
        write_permission = Permissions.check_permission(
            token=token, permission_type="write"
        )
        prod_mode = not write_permission or self.config.autoscaling_enabled

        self.feedback_logger.log(
            FeedbackLog(
                event=UpvoteLog(
                    chunk_ids=[sample.reference_id for sample in input.text_id_pairs],
                    queries=[sample.query_text for sample in input.text_id_pairs],
                    reference_texts=[
                        sample.reference_text for sample in input.text_id_pairs
                    ],
                ),
                perform_rlhf_later=prod_mode,
            )
        )

        if prod_mode:
            message = "Upvote logged successfully."
            self.logger.info(message, code=LogCode.MODEL_RLHF)
            return response(status_code=status.HTTP_202_ACCEPTED, message=message)
        else:
            if len(input.text_id_pairs) > 100:
                message = f"Number of upvote samples exceeds the maximum {input.text_id_pairs} that can be processed synchronously in an active deployment."
                self.logger.error(message, code=LogCode.MODEL_RLHF)
                return response(
                    status_code=status.HTTP_400_BAD_REQUEST, message=message
                )
            try:
                message = "Upvote applied successfully."
                self.model.upvote(input.text_id_pairs)
                self.logger.info(message, code=LogCode.MODEL_RLHF)
                return response(
                    status_code=status.HTTP_200_OK,
                    message=message,
                )
            except Exception as e:
                message = f"Error applying upvote: {e}"
                self.logger.error(message, code=LogCode.MODEL_RLHF)
                return response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=message,
                )

    @ndb_associate_metric.time()
    def associate(
        self,
        input: AssociateInput,
        token: str = Depends(Permissions.verify_permission("read")),
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
        write_permission = Permissions.check_permission(
            token=token, permission_type="write"
        )
        prod_mode = not write_permission or self.config.autoscaling_enabled

        self.feedback_logger.log(
            FeedbackLog(
                event=AssociateLog(
                    sources=[sample.source for sample in input.text_pairs],
                    targets=[sample.target for sample in input.text_pairs],
                ),
                perform_rlhf_later=prod_mode,
            )
        )

        if prod_mode:
            message = "Associate logged successfully."
            self.logger.info(message, code=LogCode.MODEL_RLHF)
            return response(
                status_code=status.HTTP_202_ACCEPTED,
                message=message,
            )
        else:
            if len(input.text_pairs) > 100:
                message = f"Number of association samples exceeds the maximum {input.text_pairs} that can be processed synchronously in an active deployment."
                self.logger.error(message, code=LogCode.MODEL_RLHF)
                return response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message=message,
                )
            try:
                message = "Associate applied successfully."
                self.model.associate(input.text_pairs)
                self.logger.info(message, code=LogCode.MODEL_RLHF)
                return response(
                    status_code=status.HTTP_200_OK,
                    message=message,
                )
            except Exception as e:
                message = f"Error applying association: {e}"
                self.logger.error(message, code=LogCode.MODEL_RLHF)
                return response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=message,
                )

    @ndb_implicit_feedback_metric.time()
    def implicit_feedback(
        self,
        feedback: ImplicitFeedbackInput,
        token: str = Depends(Permissions.verify_permission("read")),
    ):
        self.feedback_logger.log(
            FeedbackLog(
                event=ImplicitUpvoteLog(
                    chunk_id=feedback.reference_id,
                    query=feedback.query_text,
                    event_desc=feedback.event_desc,
                ),
                perform_rlhf_later=True,
            )
        )

        if feedback.reference_rank is not None and feedback.reference_rank < len(
            ndb_top_k_selections
        ):
            ndb_top_k_selections[feedback.reference_rank].inc()

        return response(
            status_code=status.HTTP_200_OK,
            message="Implicit feedback logged successfully.",
        )

    def update_chat_settings(
        self,
        settings: ChatSettings,
        token=Depends(Permissions.verify_permission("write")),
    ):
        self.model.set_chat(**(settings.model_dump()))

        return response(
            status_code=status.HTTP_200_OK,
            message="Successfully updated chat settings",
        )

    def get_chat_history(
        self,
        input: ChatHistoryInput,
        token=Depends(Permissions.verify_permission("read")),
    ):
        chat = self.model.get_chat(provider=input.provider)
        if not chat:
            raise Exception(
                f"Chat is not enabled for provider: {input.provider}. Please set up the provider."
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

        chat_history = {"chat_history": chat.get_chat_history(session_id)}

        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=chat_history,
        )

    def chat(
        self,
        input: ChatInput,
        token=Depends(Permissions.verify_permission("read")),
    ):
        chat = self.model.get_chat(provider=input.provider)
        if not chat:
            raise Exception(
                f"Chat is not enabled for provider: {input.provider}. Please set up the provider."
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

        async def generate_response() -> AsyncGenerator[str, None]:
            async for chunk in chat.stream_chat(input.user_input, session_id):
                yield chunk

        return StreamingResponse(generate_response(), media_type="text/plain")

    def get_sources(self, token=Depends(Permissions.verify_permission("read"))):
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
        sources = self.model.sources()
        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=sources,
        )

    def save(
        self,
        input: SaveModel,
        background_tasks: BackgroundTasks,
        token: str = Depends(Permissions.verify_permission("read")),
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
        model_id = self.config.model_id
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

            is_model_present = self.reporter.check_model_present(
                token, input.model_name
            )
            if is_model_present:
                return response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="Model name already exists, choose another one.",
                )
        else:
            override_permission = Permissions.check_permission(
                token=token, permission_type="override"
            )
            if not override_permission:
                return response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="You don't have permissions to override this model.",
                )

        background_tasks.add_task(self._perform_save, model_id, token, input.override)

        message = "Save operation initiated in the background."
        self.logger.info(message, code=LogCode.MODEL_SAVE)
        return response(
            status_code=status.HTTP_202_ACCEPTED,
            message=message,
            data={"new_model_id": model_id if not input.override else None},
        )

    def _perform_save(self, model_id: str, token: str, override: bool):
        try:
            self.model.save(model_id=model_id)
            if not override:
                self.reporter.save_model(
                    access_token=token,
                    model_id=model_id,
                    base_model_id=self.config.model_id,
                    model_name=model_id,
                    metadata={"thirdai_version": str(thirdai.__version__)},
                )
        except Exception as err:
            self.logger.error(
                f"Error in background save: {traceback.format_exc()}",
                code=LogCode.MODEL_SAVE,
            )

    def highlighted_pdf(
        self, reference_id: int, token=Depends(Permissions.verify_permission("read"))
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
        source, pdf_bytes = self.model.highlight_pdf(reference_id)
        buffer = io.BytesIO(pdf_bytes)
        headers = {"Content-Disposition": f'inline; filename="{Path(source).name}"'}
        return Response(
            buffer.getvalue(), headers=headers, media_type="application/pdf"
        )

    def pdf_blob(
        self, source: str, token=Depends(Permissions.verify_permission("read"))
    ):
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
        return Response(
            buffer.getvalue(), headers=headers, media_type="application/pdf"
        )

    def get_signed_url(
        self,
        source: str,
        provider: str,
        token=Depends(Permissions.verify_permission("read")),
    ):
        cloud_client = get_cloud_client(provider=provider)

        signed_url = cloud_client.generate_url_from_source(source=source)

        return response(
            status_code=status.HTTP_200_OK,
            message=f"Successfully got the signed url",
            data={"signed_url": signed_url},
        )

    def pdf_chunks(
        self, reference_id: int, token=Depends(Permissions.verify_permission("read"))
    ):
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
        if chunks := self.model.chunks(reference_id):
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

    def get_tasks(
        self,
        task_id: Optional[str] = None,
        token: str = Depends(Permissions.verify_permission("write")),
    ):
        """
        Returns list of queued insert or delete tasks
        Parameters:
        - task_id: Optional[str] - Specific task id to get info for
        - token: str - Authorization token.
        Returns:
        - JSONResponse: Dict of tasks.
        Example Response Body:
        ```
        {
            "tasks": {task_id: task_data}
        }
        ```
        """
        with self.task_lock:
            if task_id:
                return response(
                    status_code=status.HTTP_200_OK,
                    message=f"Returned task info",
                    data={"task": self.tasks.get(task_id)},
                )
            else:
                return response(
                    status_code=status.HTTP_200_OK,
                    message=f"Returned all tasks.",
                    data={"tasks": self.tasks},
                )

    def process_tasks(self):
        while True:
            task_id = self.task_queue.get()
            try:
                with self.task_lock:
                    action = self.tasks[task_id].action
                    data = self.tasks[task_id].data
                    self.tasks[task_id].status = TaskStatus.IN_PROGRESS
                    self.tasks[task_id].last_modified = now()
                if action == TaskAction.INSERT:
                    documents = data["documents"]
                    inserted_docs = self.model.insert(documents=documents)
                    with self.task_lock:
                        self.tasks[task_id].status = TaskStatus.COMPLETE
                        self.tasks[task_id].last_modified = now()
                        self.tasks[task_id].data["sources"] = inserted_docs
                elif action == TaskAction.DELETE:
                    doc_ids = data["source_ids"]
                    self.model.delete(doc_ids)
                    with self.task_lock:
                        self.tasks[task_id].status = TaskStatus.COMPLETE
                        self.tasks[task_id].last_modified = now()

            except Exception as e:
                with self.task_lock:
                    self.tasks[task_id].status = TaskStatus.FAILED
                    self.tasks[task_id].message = str(traceback.format_exc())
                    self.tasks[task_id].last_modified = now()
                    logging.error(
                        f"Task {task_id} with data {self.tasks[task_id]} failed: {str(traceback.format_exc())}"
                    )

            finally:
                with self.task_lock:
                    self.task_queue.task_done()

    def shutdown(self):
        self.logger.info(f"Shutting down NeuralDB deployment")
        self.model.cleanup()
