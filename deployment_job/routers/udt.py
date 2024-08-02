from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from permissions import Permissions
from pydantic_models.inputs import BaseQueryParams
from routers.model import get_model
from utils import propagate_error, response
from variables import GeneralVariables

udt_router = APIRouter()
permissions = Permissions()
general_variables = GeneralVariables.load_from_env()


@udt_router.post("/predict")
@propagate_error
def udt_query(
    base_params: BaseQueryParams,
    _=Depends(permissions.verify_read_permission),
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

    results = model.predict(**params)

    return response(
        status_code=status.HTTP_200_OK,
        message="Successful",
        data=jsonable_encoder(results),
    )
