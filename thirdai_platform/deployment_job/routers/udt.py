import os
import time

from deployment_job.models.classification_models import (
    ClassificationModel,
    TextClassificationModel,
    TokenClassificationModel,
)
from deployment_job.permissions import Permissions
from deployment_job.pydantic_models.inputs import (
    TextAnalysisPredictParams,
    TokenAnalysisPredictParams,
)
from deployment_job.reporter import Reporter
from deployment_job.throughput import Throughput
from fastapi import APIRouter, Depends, Query, UploadFile, status
from fastapi.encoders import jsonable_encoder
from platform_common.dependencies import is_on_low_disk
from platform_common.logging import JobLogger, LogCode
from platform_common.ndb.ndbv1_parser import convert_to_ndb_file
from platform_common.pii.data_types import (
    UnstructuredTokenClassificationResults,
    XMLTokenClassificationResults,
)
from platform_common.pydantic_models.deployment import DeploymentConfig, UDTSubType
from platform_common.thirdai_storage.data_types import (
    LabelCollection,
    LabelStatus,
    TextClassificationData,
    TokenClassificationData,
)
from platform_common.utils import response
from prometheus_client import Summary
from thirdai import neural_db as ndb

udt_predict_metric = Summary("udt_predict", "UDT predictions")

udt_query_length = Summary("udt_query_length", "Distribution of query lengths")


class UDTBaseRouter:
    def __init__(self, config: DeploymentConfig, reporter: Reporter, logger: JobLogger):
        self.model: ClassificationModel = self.get_model(config, logger)
        self.logger = logger

        # TODO(Nicholas): move these metrics to prometheus
        self.start_time = time.time()
        self.tokens_identified = Throughput()
        self.queries_ingested = Throughput()
        self.queries_ingested_bytes = Throughput()

        self.router = APIRouter()
        self.router.add_api_route("/stats", self.stats, methods=["GET"])
        self.router.add_api_route("/get-text", self.get_text, methods=["POST"])

    @staticmethod
    def get_model(config: DeploymentConfig, logger: JobLogger) -> ClassificationModel:
        raise NotImplementedError("Subclasses should implement this method")

    def get_text(
        self,
        file: UploadFile,
        _: str = Depends(Permissions.verify_permission("read")),
    ):
        """
        Process an uploaded file to extract text content.

        Args:
            file (UploadFile): The uploaded file to process.
            _ (str): Unused parameter for permission check dependency injection.

        Returns:
            A JSON response containing the extracted text content.
        """
        try:
            # Define the path where the uploaded file will be temporarily saved
            destination_path = self.model.data_dir / file.filename

            # Save the uploaded file to the temporary location
            with open(destination_path, "wb") as f:
                f.write(file.file.read())

            # Convert the file to an ndb Document object
            # This likely involves parsing and processing the file content
            doc: ndb.Document = convert_to_ndb_file(
                destination_path, metadata=None, options=None
            )

            # Extract the 'display' column from the document's table
            # and convert it to a list
            display_list = doc.table.df["display"].tolist()

            # Remove the temporary file
            os.remove(destination_path)

            self.logger.info(
                f"Processing text extraction for file: {file.filename}",
                code=LogCode.FILE_VALIDATION,
            )

            # Return a JSON response with the extracted text content
            return response(
                status_code=status.HTTP_200_OK,
                message="Successful",
                data=jsonable_encoder(display_list),
            )
        except Exception as e:
            self.logger.error(
                f"Error processing text extraction for file: {file.filename}. Error: {e}",
                code=LogCode.FILE_VALIDATION,
            )
            raise e

    def stats(self, token=Depends(Permissions.verify_permission("read"))):
        """
        Returns statistics about the deployment such as the number of tokens identified, number of
        queries ingested, and total size of queries ingested.

        Parameters:
        - token: str - Authorization token (inferred from permissions dependency).

        Returns:
        - JSONResponse: Statistics about deployment usage. Example response:
        {
            "past_hour": {
                "tokens_identified": 125,
                "queries_ingested": 12,
                "queries_ingested_bytes": 7223,
            },
            "total": {
                "tokens_identified": 1125,
                "queries_ingested": 102,
                "queries_ingested_bytes": 88101,
            },
            "uptime": 35991
        }
        uptime is given in seconds.
        """
        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data={
                "past_hour": {
                    "tokens_identified": self.tokens_identified.past_hour(),
                    "queries_ingested": self.queries_ingested.past_hour(),
                    "queries_ingested_bytes": self.queries_ingested_bytes.past_hour(),
                },
                "total": {
                    "tokens_identified": self.tokens_identified.past_hour(),
                    "queries_ingested": self.queries_ingested.past_hour(),
                    "queries_ingested_bytes": self.queries_ingested_bytes.past_hour(),
                },
                "uptime": int(time.time() - self.start_time),
            },
        )


class UDTRouterTextClassification(UDTBaseRouter):
    def __init__(self, config: DeploymentConfig, reporter: Reporter, logger: JobLogger):
        super().__init__(config, reporter, logger)
        # Add routes specific to text classification
        self.router.add_api_route(
            "/insert_sample",
            self.insert_sample,
            methods=["POST"],
            dependencies=[Depends(is_on_low_disk(path=config.model_bazaar_dir))],
        )
        self.router.add_api_route(
            "/get_recent_samples", self.get_recent_samples, methods=["GET"]
        )
        self.router.add_api_route("/predict", self.predict, methods=["POST"])

    @udt_predict_metric.time()
    def predict(
        self,
        params: TextAnalysisPredictParams,
        token=Depends(Permissions.verify_permission("read")),
    ):
        """
        Predicts the output based on the provided query parameters.

        Parameters:
        - text: str - The text for the sample to perform inference on.
        - top_k: int - The number of results to return.
        - token: str - Authorization token (inferred from permissions dependency).

        Returns:
        - JSONResponse: Prediction results.

        Example Request Body:
        ```
        {
            "text": "What is artificial intelligence?",
            "top_k": 5
        }
        ```
        """
        start_time = time.perf_counter()

        text_length = len(params.text.split())
        udt_query_length.observe(text_length)

        results = self.model.predict(**params.model_dump())
        self.queries_ingested.log(1)
        self.queries_ingested_bytes.log(len(params.text))

        end_time = time.perf_counter()
        time_taken = end_time - start_time

        # Add time_taken to the response data
        response_data = {
            "prediction_results": jsonable_encoder(results),
            "time_taken": time_taken,
        }

        self.logger.debug(f"Prediction complete with time taken: {time_taken} seconds")

        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=response_data,
        )

    @staticmethod
    def get_model(config: DeploymentConfig, logger: JobLogger) -> ClassificationModel:
        subtype = config.model_options.udt_sub_type
        logger.info(
            f"Initializing Text Classification model of subtype: {subtype}",
            code=LogCode.MODEL_INIT,
        )
        if subtype == UDTSubType.text or subtype == UDTSubType.document:
            return TextClassificationModel(config=config, logger=logger)
        else:
            error_message = (
                f"Unsupported UDT subtype '{subtype}' for Text Classification."
            )
            logger.error(error_message, code=LogCode.MODEL_INIT)
            raise ValueError(error_message)

    def insert_sample(
        self,
        sample: TextClassificationData,
        token=Depends(Permissions.verify_permission("write")),
    ):
        self.model.insert_sample(sample)
        return response(status_code=status.HTTP_200_OK, message="Successful")

    def get_recent_samples(
        self,
        num_samples: int = Query(
            default=5, ge=1, le=100, description="Number of recent samples to retrieve"
        ),
        token: str = Depends(Permissions.verify_permission("read")),
    ):
        recent_samples = self.model.get_recent_samples(num_samples=num_samples)
        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=jsonable_encoder(recent_samples),
        )


class UDTRouterTokenClassification(UDTBaseRouter):
    def __init__(self, config: DeploymentConfig, reporter: Reporter, logger: JobLogger):
        super().__init__(config, reporter, logger)
        # The following routes are only applicable for token classification models
        # TODO(Shubh): Make different routers for text and token classification models
        self.router.add_api_route("/add_labels", self.add_labels, methods=["POST"])
        self.router.add_api_route(
            "/insert_sample",
            self.insert_sample,
            methods=["POST"],
            dependencies=[Depends(is_on_low_disk(path=config.model_bazaar_dir))],
        )
        self.router.add_api_route("/get_labels", self.get_labels, methods=["GET"])
        self.router.add_api_route(
            "/get_recent_samples", self.get_recent_samples, methods=["GET"]
        )
        self.router.add_api_route("/predict", self.predict, methods=["POST"])

    @staticmethod
    def get_model(config: DeploymentConfig, logger: JobLogger) -> ClassificationModel:
        subtype = config.model_options.udt_sub_type
        logger.info(
            f"Initializing Token Classification model of subtype: {subtype}",
            code=LogCode.MODEL_INIT,
        )
        if subtype == UDTSubType.token:
            return TokenClassificationModel(config=config, logger=logger)
        else:
            error_message = (
                f"Unsupported UDT subtype '{subtype}' for Token Classification."
            )
            logger.error(error_message, code=LogCode.MODEL_INIT)
            raise ValueError(error_message)

    def add_labels(
        self,
        labels: LabelCollection,
        token=Depends(Permissions.verify_permission("write")),
    ):
        """
        Adds new labels to the model.
        Parameters:
        - labels: LabelEntityList - A list of LabelEntity specifying the name of the label and description for generating synthetic data for the label.
        - token: str - Authorization token (inferred from permissions dependency).
        Returns:
        - JSONResponse: Status specifying whether or not the request to add labels was successful.

        Example Request Body:
        ```
        {
            "tags": [
                {
                    "name": "label1",
                    "description": "Description for label1"
                },
                {
                    "name": "label2",
                    "description": "Description for label2"
                }
            ]
        }
        ```
        """

        for label in labels.tags:
            assert label.status == LabelStatus.uninserted
        self.model.add_labels(labels)
        return response(status_code=status.HTTP_200_OK, message="Successful")

    def insert_sample(
        self,
        sample: TokenClassificationData,
        token=Depends(Permissions.verify_permission("write")),
    ):
        """
        Inserts a sample into the model.
        Parameters:
        - sample: TokenClassificationSample - The sample to insert into the model.
        - token: str - Authorization token (inferred from permissions dependency).
        Returns:
        - JSONResponse: Status specifying whether or not the request to insert a sample was successful.

        Example Request Body:
        ```
        {
            "tokens": ["This", "is", "a", "test", "sample"],
            "tags": ["O", "O", "O", "test_label", "O"]
        }
        ```
        """
        self.model.insert_sample(sample)
        return response(status_code=status.HTTP_200_OK, message="Successful")

    def get_labels(self, token=Depends(Permissions.verify_permission("read"))):
        """
        Retrieves the labels from the model.
        Parameters:
        - token: str - Authorization token (inferred from permissions dependency).
        Returns:
        - JSONResponse: The labels from the model.
        """
        labels = self.model.get_labels()
        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=jsonable_encoder(labels),
        )

    def get_recent_samples(
        self,
        num_samples: int = Query(
            default=5, ge=1, le=100, description="Number of recent samples to retrieve"
        ),
        token: str = Depends(Permissions.verify_permission("read")),
    ):
        """
        Retrieves the most recent samples from the model.

        Parameters:
        - num_samples: int - Number of recent samples to retrieve (default: 5, min: 1, max: 100)
        - token: str - Authorization token (inferred from permissions dependency)

        Returns:
        - JSONResponse: The most recent samples from the model
        """
        recent_samples = self.model.get_recent_samples(num_samples=num_samples)
        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=jsonable_encoder(recent_samples),
        )

    @udt_predict_metric.time()
    def predict(
        self,
        params: TokenAnalysisPredictParams,
        token=Depends(Permissions.verify_permission("read")),
    ):
        """
        Predicts the output based on the provided query parameters.

        Parameters:
        - text: str - The text for the sample to perform inference on
        - top_k: int - The number of results to return
        - data_type: str - The data type of the text. (unstructured or xml)
        - token: str - Authorization token (inferred from permissions dependency).

        Returns:
        - JSONResponse: Prediction results.

        Example Request Body:
        ```
        {
            "text": "What is artificial intelligence?",
            "top_k": 5,
            "data_type": "unstructured"
        }
        ```
        """
        start_time = time.perf_counter()

        text_length = len(params.text.split())
        udt_query_length.observe(text_length)

        results = self.model.predict(**params.model_dump())
        self.queries_ingested.log(1)
        self.queries_ingested_bytes.log(len(params.text))

        # TODO(pratik/geordie/yash): Add logging for search results text classification
        if isinstance(results, UnstructuredTokenClassificationResults):
            identified_count = len(
                [tags[0] for tags in results.predicted_tags if tags[0] != "O"]
            )
            self.tokens_identified.log(identified_count)
            self.logger.debug(
                f"Prediction complete with {identified_count} tokens identified",
                text_length=len(params.text),
            )

        elif isinstance(results, XMLTokenClassificationResults):
            self.tokens_identified.log(len(results.predictions))
            self.logger.debug(
                f"Prediction complete with {len(results.predictions)} predictions",
                text_length=len(params.text),
            )

        end_time = time.perf_counter()
        time_taken = end_time - start_time

        # Add time_taken to the response data
        response_data = {
            "prediction_results": jsonable_encoder(results),
            "time_taken": time_taken,
        }

        self.logger.debug(f"Prediction complete with time taken: {time_taken} seconds")

        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=response_data,
        )
