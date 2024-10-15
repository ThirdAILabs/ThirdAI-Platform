import os
import time

from config import DeploymentConfig, UDTSubType
from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.encoders import jsonable_encoder
from models.ndbv1_parser import convert_to_ndb_file
from models.classification_models import (
    ClassificationModel,
    TextClassificationModel,
    TokenClassificationModel,
)
from permissions import Permissions
from prometheus_client import Summary
from pydantic_models.inputs import (
    SearchResultsTokenClassification,
    TextAnalysisPredictParams,
)
from reporter import Reporter
from common.thirdai_storage.data_types import (
    LabelCollection,
    LabelStatus,
    TokenClassificationData,
)
from throughput import Throughput
from utils import propagate_error, response
from thirdai import neural_db as ndb

udt_predict_metric = Summary("udt_predict", "UDT predictions")


class UDTRouter:
    def __init__(self, config: DeploymentConfig, reporter: Reporter):
        self.model: ClassificationModel = UDTRouter.get_model(config)

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
    def get_model(config: DeploymentConfig) -> ClassificationModel:
        subtype = config.model_options.udt_sub_type
        if subtype == UDTSubType.text:
            return TextClassificationModel(config=config)
        elif subtype == UDTSubType.token:
            return TokenClassificationModel(config=config)
        else:
            raise ValueError(f"Unsupported UDT subtype '{subtype}'.")

    @propagate_error
    def get_text(
        self,
        file: UploadFile,
        _: str = Depends(Permissions.verify_permission("read")),
    ):
        destination_path = self.model.data_dir / file.filename
        with open(destination_path, "wb") as f:
            f.write(file.file.read())
            
        doc: ndb.Document = convert_to_ndb_file(destination_path, metadata=None, options=None)
        
        display_list = doc.table.df['display'].tolist()
        
        os.remove(destination_path)
        
        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=jsonable_encoder(display_list),
        )
        

    @propagate_error
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
            self.tokens_identified.log(
                len([tags[0] for tags in results.predicted_tags if tags[0] != "O"])
            )
            self.queries_ingested.log(1)
            self.queries_ingested_bytes.log(len(params.text))

        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=jsonable_encoder(results),
        )

    @propagate_error
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

    @propagate_error
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

    @propagate_error
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

    @propagate_error
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

    @propagate_error
    def get_recent_samples(self, token=Depends(Permissions.verify_permission("read"))):
        """
        Retrieves the most recent samples from the model.
        Parameters:
        - token: str - Authorization token (inferred from permissions dependency).
        Returns:
        - JSONResponse: The most recent samples from the model.
        """
        recent_samples = self.model.get_recent_samples(
            limit=5
        )  # Fetch 5 most recent samples
        # We're not modifying the samples here as they're already in the correct format
        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=jsonable_encoder(recent_samples),
        )
