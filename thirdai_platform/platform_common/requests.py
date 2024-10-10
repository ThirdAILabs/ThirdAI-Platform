from typing import Dict

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def response(
    status_code: int, message: str, data: Dict = {}, success: bool = None
) -> JSONResponse:
    """
    Creates a JSON response with a given status code, message, and data.

    Args:
        status_code (int): HTTP status code.
        message (str): Message to include in the response.
        data (Dict, optional): Data to include in the response. Defaults to {}.
        success (bool, optional): Indicates success or failure. Defaults to None.

    Returns:
        JSONResponse: The JSON response.
    """
    if success is not None:
        status = "success" if success else "failed"
    else:
        status = "success" if status_code < 400 else "failed"
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "message": message, "data": jsonable_encoder(data)},
    )
