import time

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from permissions import Permissions
from prometheus_client import Summary
from pydantic_models.inputs import BaseQueryParams, SearchResultsTokenClassification
from routers.model import get_model
from throughput import Throughput
from utils import propagate_error, response

udt_router = APIRouter()
permissions = Permissions()


start_time = time.time()
tokens_identified = Throughput()
queries_ingested = Throughput()
queries_ingested_bytes = Throughput()


udt_predict_metric = Summary("udt_predict", "UDT predictions")


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
