import os
import time
from logging import Logger

from deployment_job.models.classification_models import (
    ClassificationModel,
    TextClassificationModel,
    TokenClassificationModel,
)
from deployment_job.permissions import Permissions
from deployment_job.pydantic_models.inputs import (
    SearchResultsTokenClassification,
    TextAnalysisPredictParams,
)
from deployment_job.reporter import Reporter
from fastapi import APIRouter, Depends, Query, UploadFile, status
from fastapi.encoders import jsonable_encoder
from platform_common.ndb.ndbv1_parser import convert_to_ndb_file
from platform_common.pydantic_models.deployment import DeploymentConfig, UDTSubType
from platform_common.thirdai_storage.data_types import (
    LabelCollection,
    LabelStatus,
    TokenClassificationData,
)
from platform_common.utils import response
from prometheus_client import Summary
from reporter import Reporter
from thirdai import neural_db as ndb
from throughput import Throughput

udt_predict_metric = Summary("udt_predict", "UDT predictions")


class UDTRouter:
    def __init__(self, config: DeploymentConfig, reporter: Reporter, logger: Logger):
        self.model: ClassificationModel = UDTRouter.get_model(config, logger)
        self.logger = logger

        # TODO(Nicholas): move these metrics to prometheus
        self.start_time = time.time()
        self.tokens_identified = Throughput()
        self.queries_ingested = Throughput()
        self.queries_ingested_bytes = Throughput()

        self.router = APIRouter()
        self.router.add_api_route("/predict", self.predict, methods=["POST"])
        self.router.add_api_route("/stats", self.stats, methods=["GET"])
        self.router.add_api_route("/get-text", self.get_text, methods=["POST"])

        # The following routes are only applicable for token classification models
        # TODO(Shubh) : Make different routers for text and token classification models
        if self.model.config.model_options.udt_sub_type == UDTSubType.token:
            self.router.add_api_route("/add_labels", self.add_labels, methods=["POST"])
            self.router.add_api_route(
                "/insert_sample", self.insert_sample, methods=["POST"]
            )
            self.router.add_api_route("/get_labels", self.get_labels, methods=["GET"])
            self.router.add_api_route(
                "/get_recent_samples", self.get_recent_samples, methods=["GET"]
            )

    @staticmethod
    def get_model(config: DeploymentConfig, logger: Logger) -> ClassificationModel:
        subtype = config.model_options.udt_sub_type
        logger.info(f"Initializing model of subtype: {subtype}")
        if subtype == UDTSubType.text:
            return TextClassificationModel(config=config, logger=logger)
        elif subtype == UDTSubType.token:
            return TokenClassificationModel(config=config, logger=logger)
        else:
            error_message = f"Unsupported UDT subtype '{subtype}'."
            logger.error(error_message)
            raise ValueError(error_message)

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
        self.logger.info(f"Processing text extraction for file: {file.filename}")
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

        # Return a JSON response with the extracted text content
        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=jsonable_encoder(display_list),
        )

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
        results = self.model.predict(**params.model_dump())

        # TODO(pratik/geordie/yash): Add logging for search results text classification
        if isinstance(results, SearchResultsTokenClassification):
            identified_count = len(
                [tags[0] for tags in results.predicted_tags if tags[0] != "O"]
            )
            self.tokens_identified.log(identified_count)
            self.queries_ingested.log(1)
            self.queries_ingested_bytes.log(len(params.text))
            self.logger.info(
                f"Prediction complete with {identified_count} tokens identified",
                extra={"text_length": len(params.text)},
            )

        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=jsonable_encoder(results),
        )

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
