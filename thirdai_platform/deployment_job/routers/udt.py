import time

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
from deployment_job.utils import propagate_error
from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from platform_common.pydantic_models.deployment import DeploymentConfig, UDTSubType
from platform_common.utils import response
from prometheus_client import Summary
from throughput import Throughput

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
