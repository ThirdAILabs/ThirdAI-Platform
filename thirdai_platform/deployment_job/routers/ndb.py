import io
import traceback
import uuid
from pathlib import Path
from typing import AsyncGenerator, List

import fitz
import jwt
import thirdai
from config import DeploymentConfig, NDBSubType
from fastapi import APIRouter, Depends, Form, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from models.ndb_models import NDBModel, NDBV1Model, NDBV2Model
from permissions import Permissions
from platform_common.file_handler import download_local_files
from platform_common.requests import response
from prometheus_client import Counter, Summary
from pydantic import ValidationError
from pydantic_models import inputs
from pydantic_models.inputs import NDBSearchParams
from reporter import Reporter
from update_logger import (
    AssociateLog,
    DeleteLog,
    FeedbackLog,
    ImplicitUpvoteLog,
    InsertLog,
    UpdateLogger,
    UpvoteLog,
)
from utils import propagate_error, validate_name

ndb_query_metric = Summary("ndb_query", "NDB Queries")
ndb_upvote_metric = Summary("ndb_upvote", "NDB upvotes")
ndb_associate_metric = Summary("ndb_associate", "NDB associations")
ndb_implicit_feedback_metric = Summary("ndb_implicit_feedback", "NDB implicit feedback")
ndb_insert_metric = Summary("ndb_insert", "NDB insertions")
ndb_delete_metric = Summary("ndb_delete", "NDB deletions")

ndb_top_k_selections = Counter(
    "ndb_top_k_selections", "Number of top-k results selected by user."
)


class NDBRouter:
    def __init__(self, config: DeploymentConfig, reporter: Reporter):
        self.config = config
        self.reporter = reporter

        self.model: NDBModel = NDBRouter.get_model(config)

        self.feedback_logger = UpdateLogger.get_feedback_logger(self.model.data_dir)
        self.insertion_logger = UpdateLogger.get_insertion_logger(self.model.data_dir)
        self.deletion_logger = UpdateLogger.get_deletion_logger(self.model.data_dir)

        self.router = APIRouter()
        self.router.add_api_route("/search", self.search, methods=["POST"])
        self.router.add_api_route("/insert", self.insert, methods=["POST"])
        self.router.add_api_route("/delete", self.delete, methods=["POST"])
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
        self.router.add_api_route("/save", self.save, methods=["POST"])
        self.router.add_api_route(
            "/highlighted-pdf", self.highlighted_pdf, methods=["GET"]
        )
        self.router.add_api_route("/pdf-blob", self.pdf_blob, methods=["GET"])
        self.router.add_api_route("/pdf-chunks", self.pdf_chunks, methods=["GET"])

    @staticmethod
    def get_model(config: DeploymentConfig) -> NDBModel:
        subtype = config.model_options.ndb_sub_type
        if subtype == NDBSubType.v1:
            return NDBV1Model(config=config, write_mode=not config.autoscaling_enabled)
        elif subtype == NDBSubType.v2:
            return NDBV2Model(config=config, write_mode=not config.autoscaling_enabled)
        else:
            raise ValueError(f"Unsupported NDB subtype '{subtype}'.")

    @ndb_query_metric.time()
    @propagate_error
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

    @propagate_error
    @ndb_insert_metric.time()
    def insert(
        self,
        documents: str = Form(...),
        files: List[UploadFile] = [],
        token: str = Depends(Permissions.verify_permission("write")),
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
            documents = inputs.DocumentList.model_validate_json(documents).documents
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
            dest_dir=self.model.data_dir / "insertions" / "documents",
        )

        if self.config.autoscaling_enabled:
            self.insertion_logger.log(InsertLog(documents=documents))

            return response(
                status_code=status.HTTP_202_ACCEPTED,
                message="Insert logged successfully.",
            )
        else:
            self.model.insert(documents=documents)

            return response(
                status_code=status.HTTP_200_OK,
                message="Insert applied successfully.",
            )

    @propagate_error
    @ndb_delete_metric.time()
    def delete(
        self,
        input: inputs.DeleteInput,
        token: str = Depends(Permissions.verify_permission("write")),
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

        if self.config.autoscaling_enabled:
            self.deletion_logger.log(DeleteLog(doc_ids=input.source_ids))

            return response(
                status_code=status.HTTP_202_ACCEPTED,
                message="Delete logged successfully.",
            )
        else:
            self.model.delete(input.source_ids)

            return response(
                status_code=status.HTTP_200_OK,
                message="Delete applied successfully.",
            )

    @propagate_error
    @ndb_upvote_metric.time()
    def upvote(
        self,
        input: inputs.UpvoteInput,
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

        if not write_permission or self.config.autoscaling_enabled:
            self.feedback_logger.log(
                FeedbackLog(
                    event=UpvoteLog(
                        chunk_ids=[
                            sample.reference_id for sample in input.text_id_pairs
                        ],
                        queries=[sample.query_text for sample in input.text_id_pairs],
                    )
                )
            )
            return response(
                status_code=status.HTTP_202_ACCEPTED,
                message="Upvote logged successfully.",
            )
        else:
            self.model.upvote(input.text_id_pairs)

            return response(
                status_code=status.HTTP_200_OK,
                message="Upvote applied successfully.",
            )

    @propagate_error
    @ndb_associate_metric.time()
    def associate(
        self,
        input: inputs.AssociateInput,
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

        if not write_permission or self.config.autoscaling_enabled:
            self.feedback_logger.log(
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
            self.model.associate(input.text_pairs)

            return response(
                status_code=status.HTTP_200_OK,
                message="Associate applied successfully.",
            )

    @propagate_error
    @ndb_implicit_feedback_metric.time()
    def implicit_feedback(
        self,
        feedback: inputs.ImplicitFeedbackInput,
        token: str = Depends(Permissions.verify_permission("read")),
    ):
        self.feedback_logger.log(
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

    @propagate_error
    def update_chat_settings(
        self,
        settings: inputs.ChatSettings,
        token=Depends(Permissions.verify_permission("write")),
    ):
        self.model.set_chat(**(settings.model_dump()))

        return response(
            status_code=status.HTTP_200_OK,
            message="Successfully updated chat settings",
        )

    @propagate_error
    def get_chat_history(
        self,
        input: inputs.ChatHistoryInput,
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

    @propagate_error
    def chat(
        self,
        input: inputs.ChatInput,
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

    @propagate_error
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
        input: inputs.SaveModel,
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
        try:
            self.model.save(model_id=model_id)
            if not input.override:
                self.reporter.save_model(
                    access_token=token,
                    model_id=model_id,
                    base_model_id=self.config.model_id,
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

    @propagate_error
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

    @propagate_error
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

    @propagate_error
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
