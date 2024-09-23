import time

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from permissions import Permissions
from models.classification_models import (
    TextClassificationModel,
    TokenClassificationModel,
)
from prometheus_client import Summary
from pydantic_models.inputs import BaseQueryParams, SearchResultsTokenClassification
from routers.model import get_model
from throughput import Throughput
from utils import propagate_error, response
from config import DeploymentConfig, UDTSubType

udt_router = APIRouter()
permissions = Permissions()


udt_predict_metric = Summary("udt_predict", "UDT predictions")


class UDTRouter:
    def __init__(self, config: DeploymentConfig, permissions: Permissions):
        self.config = config
        self.permissions = permissions

        sub_type = self.config.model_options.udt_sub_type
        if sub_type == UDTSubType.text:
            self.model = TextClassificationModel(
                model_bazaar_dir=self.config.model_bazaar_dir,
                model_id=self.config.model_id,
            )
        elif sub_type == UDTSubType.token:
            self.model = TokenClassificationModel(
                model_bazaar_dir=self.config.model_bazaar_dir,
                model_id=self.config.model_id,
            )
        else:
            raise ValueError(f"Unhandled udt_sub_type '{sub_type}'.")

        self.start_time = time.time()
        self.tokens_identified = Throughput()
        self.queries_ingested = Throughput()
        self.queries_ingested_bytes = Throughput()

    def predict(base_params: BaseQueryParams, token=Depends(self.p))


@udt_router.post("/predict")
@propagate_error
@udt_predict_metric.time()
def udt_query(
    base_params: BaseQueryParams,
    token=Depends(permissions.verify_permission("read")),
):
    """
    Predicts the output based on the provided query parameters.

    Parameters:
    - base_params: BaseQueryParams - The base query parameters required for prediction.
    - token: str - Authorization token (inferred from permissions dependency).

    Returns:
    - JSONResponse: Prediction results.

    Example Request Body:
    ```
    {
        "query": "What is artificial intelligence?",
        "top_k": 5
    }
    ```
    """
    model = get_model()
    params = base_params.dict()

    results = model.predict(**params, token=token)

    # TODO(pratik/geordie/yash): Add logging for search results text classification
    if isinstance(results, SearchResultsTokenClassification):
        tokens_identified.log(
            len([tags[0] for tags in results.predicted_tags if tags[0] != "O"])
        )
        queries_ingested.log(1)
        queries_ingested_bytes.log(len(params["query"]))

    return response(
        status_code=status.HTTP_200_OK,
        message="Successful",
        data=jsonable_encoder(results),
    )


@udt_router.get("/stats")
@propagate_error
def udt_query(_=Depends(permissions.verify_permission("read"))):
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
                "tokens_identified": tokens_identified.past_hour(),
                "queries_ingested": queries_ingested.past_hour(),
                "queries_ingested_bytes": queries_ingested_bytes.past_hour(),
            },
            "total": {
                "tokens_identified": tokens_identified.past_hour(),
                "queries_ingested": queries_ingested.past_hour(),
                "queries_ingested_bytes": queries_ingested_bytes.past_hour(),
            },
            "uptime": int(time.time() - start_time),
        },
    )
