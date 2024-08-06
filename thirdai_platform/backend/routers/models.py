import os
import uuid
from typing import Annotated, Dict, List, Optional, Union

from auth.jwt import AuthenticatedUser, verify_access_token
from backend.utils import (
    get_expiry_min,
    get_high_level_model_info,
    get_model,
    get_model_from_identifier,
    model_accessible,
    response,
    validate_name,
)
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, Header, Query, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload
from storage import interface, local

model_router = APIRouter()

storage: interface.StorageInterface = local.LocalStorage(
    os.getenv("LOCAL_TEST_DIR", "/model_bazaar")
)


@model_router.get("/public-list")
def list_public_models(
    name: str,
    domain: Optional[str] = None,
    username: Optional[str] = None,
    type: Optional[str] = None,
    sub_type: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """
    List public models.

    Parameters:
    - name: str - The name to filter models.
    - domain: Optional[str] - Optional domain to filter models.
    - username: Optional[str] - Optional username to filter models.
    - type: Optional[str] - Optional type to filter models.
    - sub_type: Optional[str] - Optional sub-type to filter models.
    - session: Session - The database session (dependency).

    Returns:
    - JSONResponse - A JSON response with the list of public models.
    """
    results = (
        session.query(schema.Model)
        .options(joinedload(schema.Model.user))
        .filter(
            schema.Model.name.ilike(f"%{name}%"),
            schema.Model.access_level == schema.Access.public,
        )
    )

    results = results.filter(schema.Model.train_status == schema.Status.complete)

    if domain:
        results = results.filter(schema.Model.domain == domain)

    if username:
        results = results.filter(schema.Model.user.username == username)

    if type:
        results = results.filter(schema.Model.type == type)

    if sub_type:
        results = results.filter(schema.Model.sub_type == sub_type)

    results = [get_high_level_model_info(result) for result in results]

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the public list",
        data=jsonable_encoder(results),
    )


@model_router.get("/list")
def list_models(
    name: str,
    domain: Optional[str] = None,
    username: Optional[str] = None,
    type: Optional[str] = None,
    sub_type: Optional[str] = None,
    access_level: Annotated[Union[list[str], None], Query()] = None,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    List models based on the given name, domain, username, type, sub-type, and access level.

    Parameters:
    - name: str - The name to filter models.
    - domain: Optional[str] - Optional domain to filter models.
    - username: Optional[str] - Optional username to filter models.
    - type: Optional[str] - Optional type to filter models.
    - sub_type: Optional[str] - Optional sub-type to filter models.
    - access_level: Annotated[Union[list[str], None], Query()] - Optional access level to filter models.
    - session: Session - The database session (dependency).
    - authenticated_user: AuthenticatedUser - The authenticated user (dependency).

    Returns:
    - JSONResponse - A JSON response with the list of models.
    """
    user: schema.User = authenticated_user.user

    results = (
        session.query(schema.Model)
        .options(joinedload(schema.Model.user))
        .filter(
            schema.Model.name.ilike(f"%{name}%"),
            or_(
                # public
                schema.Model.access_level == schema.Access.public,
                # protected and matching domain
                and_(
                    schema.Model.access_level == schema.Access.protected,
                    schema.Model.domain == user.domain,
                ),
                # private and matching user or admin
                and_(
                    schema.Model.access_level == schema.Access.private,
                    or_(
                        schema.Model.user_id == user.id,
                        schema.User.id == user.id,
                    ),
                ),
            ),
            schema.Model.train_status == schema.Status.complete,
        )
    )

    if domain:
        results = results.filter(schema.Model.domain == domain)

    if username:
        results = results.filter(schema.Model.user.username == username)

    if type:
        results = results.filter(schema.Model.type == type)

    if sub_type:
        results = results.filter(schema.Model.sub_type == sub_type)

    if access_level:
        conditions = []
        for access in access_level:
            conditions.append(schema.Model.access_level == access)

        # We have to unpack the conditions to be able to processed by `or_` function.
        results = results.filter(or_(*conditions))

    results = [get_high_level_model_info(result) for result in results]

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the list",
        data=jsonable_encoder(results),
    )


@model_router.get("/name-check")
def check_model(
    name: str,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Check if a model with the given name exists for the authenticated user.

    Parameters:
    - name: The name of the model to check.
    - session: The database session (dependency).
    - authenticated_user: The authenticated user (dependency).

    Returns:
    - A JSON response indicating if the model is present.
    """
    user: schema.User = authenticated_user.user
    model: schema.Model = (
        session.query(schema.Model)
        .filter(and_(schema.Model.name == name, schema.Model.user_id == user.id))
        .first()
    )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully checked for model name",
        data={"model_present": True if model else False},
    )


class SaveNDBDeployedModel(BaseModel):
    deployment_id: str
    model_id: str
    base_model_id: str
    model_name: str
    metadata: Dict[str, str]


@model_router.post("/save-deployed")
def save_deployed_model(
    body: SaveNDBDeployedModel,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Save a deployed model.

    Parameters:
    - body: The body of the request containing deployment details.
    - session: The database session (dependency).
    - authenticated_user: The authenticated user (dependency).

    Returns:
    - A JSON response indicating the status of saving the model.
    """
    user: schema.User = authenticated_user.user
    base_model: schema.Model = session.query(schema.Model).get(body.base_model_id)
    user: schema.User = session.query(schema.User).get(user.id)

    new_model = schema.Model(
        id=body.model_id,
        name=body.model_name,
        train_status=schema.Status.complete,
        access_level=schema.Access.private,
        domain=user.email.split("@")[1],
        user_id=user.id,
        parent_deployment_id=body.deployment_id,
        parent_id=base_model.id,
        type=base_model.type,
        sub_type=base_model.sub_type,
    )

    session.add(new_model)
    session.commit()
    session.refresh(new_model)

    metadata: schema.MetaData = schema.MetaData(
        model_id=body.model_id, deployment=body.metadata
    )

    session.add(metadata)
    session.commit()

    return {"message": "successfully added the model."}


@model_router.get("/pending-train-models")
def pending_train_models(
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Get a list of all in progress or not started training models for the logged-in user.

    Returns models that are in progress or not started.
    """
    user: schema.User = authenticated_user.user

    pending_model_train: List[schema.Model] = (
        session.query(schema.Model)
        .filter(
            schema.Model.user_id == user.id,
            schema.Model.train_status.in_(
                [schema.Status.in_progress, schema.Status.not_started]
            ),
        )
        .all()
    )

    results = [
        {
            "model_name": result.name,
            "status": result.train_status,
            "username": user.username,
        }
        for result in pending_model_train
    ]

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully fetched the pending list",
        data=jsonable_encoder(results),
    )


@model_router.get("/upload-token")
def upload_token(
    model_name: str,
    size: int,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Generates a token for uploading a model to the Model Bazaar.

    - **model_name**: name that the uploaded model will take in the Model Bazaar.
    - **size**: size of model to be uploaded.

    Returns a token, which is used to upload chunks of a model.
    """
    user: schema.User = authenticated_user.user
    try:
        validate_name(model_name)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    model: schema.Model = get_model(
        session, username=user.username, model_name=model_name
    )

    if model:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"There is already a model saved with {model_name}",
        )

    model_id = str(uuid.uuid4())

    token = storage.create_upload_token(
        model_identifier=f"{user.username}/{model_name}",
        user_id=str(user.id),
        model_id=model_id,
        expiration_min=get_expiry_min(size),
    )

    return response(
        status_code=status.HTTP_200_OK,
        message="Sucessfully got the upload url",
        data={"token": token},
    )


@model_router.post("/upload-chunk")
def upload_chunk(
    chunk: UploadFile,
    chunk_number: int,
    model_type: str = "ndb",
    compressed: bool = True,
    authorization: str = Header(None),
):
    """
    Uploads a chunk of a zipped NeuralDB model.

    - **chunk**: the raw bytes of the chunk.
    - **chunk_number**: the position of the chunk of the zipped NeuralDB that is being uploaded.
    - **authorization**: Bearer token that contains the token generated from /upload-token.

    """
    if authorization is None:
        return response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authentication Scheme",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not token:
            return response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization token is missing",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except ValueError:
        return response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = storage.verify_upload_token(token)
    except Exception as error:
        return response(status_code=status.HTTP_401_UNAUTHORIZED, message=str(error))

    try:
        chunk_data = chunk.file.read()
        storage.upload_chunk(
            payload["model_id"], chunk_data, chunk_number, model_type, compressed
        )
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Uploaded chunk",
    )


class ModelInfo(BaseModel):
    type: str
    sub_type: Optional[str] = None
    access_level: schema.Access = "public"
    metadata: Optional[Dict[str, str]] = None


@model_router.post("/upload-commit")
def upload_commit(
    total_chunks: int,
    body: ModelInfo,
    authorization: str = Header(None),
    session: Session = Depends(get_session),
):
    if authorization is None:
        return response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authentication Scheme",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not token:
            return response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization token is missing",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except ValueError:
        return response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = storage.verify_upload_token(token)
    except Exception as error:
        return response(status_code=status.HTTP_401_UNAUTHORIZED, message=str(error))

    model_name = payload["model_identifier"].split("/")[1]
    model: schema.Model = (
        session.query(schema.Model)
        .filter(
            schema.Model.user_id == payload["user_id"], schema.Model.name == model_name
        )
        .first()
    )

    if model:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"There is already a model saved with {model_name}",
        )

    try:
        storage.commit_upload(payload["model_id"], total_chunks)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    user: schema.User = session.query(schema.User).get(payload["user_id"])
    domain = user.email.split("@")[1]

    try:
        new_model = schema.Model(
            id=payload["model_id"],
            name=model_name,
            access_level=body.access_level,
            type=body.type,
            sub_type=body.sub_type,
            domain=domain,
            user_id=payload["user_id"],
            train_status=schema.Status.complete,
        )

        session.add(new_model)
        session.commit()
        session.refresh(new_model)
    except Exception as err:
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(err),
        )

    if body.metadata:
        new_metadata = schema.MetaData(
            model_id=payload["model_id"],
            general=body.metadata,
        )

        session.add(new_metadata)
        session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="Committed model",
    )


@model_router.get("/public-download")
def download_public_model(
    model_identifier: str,
    session: Session = Depends(get_session),
):
    """
    Downloads specified public model. No login required.

    - **model_identifier**: model identifier of model to be downloaded.

    Streams download of the model to the caller.
    """
    try:
        model: schema.Model = get_model_from_identifier(model_identifier, session)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    if model.access_level != "public":
        return response(
            status_code=status.HTTP_403_FORBIDDEN,
            message="You cannot access this model without login.",
        )

    model.downloads += 1
    session.commit()

    # Determine if the model should be compressed
    compressed = model.type == "ndb"
    storage.prepare_download(model.id, model_type=model.type, compressed=compressed)

    def iterfile():
        for chunk in storage.download_chunk_stream(
            model.id, block_size=8192, model_type=model.type, compressed=compressed
        ):
            yield chunk

    # Set the appropriate filename based on the model type and compression
    if compressed:
        filename = f"{model_identifier}.{model.type}.zip"
        media_type = "application/zip"
    else:
        filename = f"{model_identifier}.{model.type}"
        media_type = "application/octet-stream"

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return StreamingResponse(iterfile(), headers=headers, media_type=media_type)


@model_router.post("/rag-entry")
def add_rag_entry(
    model_name: str,
    ndb_model_id: Optional[str] = None,
    use_llm_guardrail: Optional[bool] = False,
    token_model_id: Optional[str] = None,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    user: schema.User = authenticated_user.user

    # Create new model entry
    new_model = schema.Model(
        user_id=user.id,
        train_status=schema.Status.complete,
        name=model_name,
        type="rag",
        domain=user.email.split("@")[1],
        access_level=schema.Access.private,
    )

    session.add(new_model)
    session.commit()
    session.refresh(new_model)

    # Prepare the general metadata dictionary
    general_metadata = {}

    if ndb_model_id is not None:
        general_metadata["ndb_model_id"] = ndb_model_id

    if use_llm_guardrail is not None:
        general_metadata["use_llm_guardrail"] = use_llm_guardrail

    if token_model_id is not None:
        general_metadata["token_model_id"] = token_model_id

    # Create new metadata entry
    new_metadata = schema.MetaData(model_id=new_model.id, general=general_metadata)

    session.add(new_metadata)
    session.commit()

    return response(
        status_code=status.HTTP_201_CREATED,
        message="Successfully added new RAG entry.",
        data={
            "model_id": str(new_model.id),
            "model_name": new_model.name,
            "metadata": jsonable_encoder(general_metadata),
        },
    )

@model_router.get("/download")
def download_model(
    model_identifier: str,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Downloads specified model.

    - **model_identifier**: model identifier of model to be downloaded.

    Streams download of the model to the caller.
    """
    try:
        model: schema.Model = get_model_from_identifier(model_identifier, session)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    if not model_accessible(model, authenticated_user.user):
        return response(
            status_code=status.HTTP_403_FORBIDDEN,
            message="You don't have access to download this model.",
        )

    model.downloads += 1
    session.commit()

    # Determine if the model should be compressed
    compressed = model.type == "ndb"
    storage.prepare_download(model.id, model_type=model.type, compressed=compressed)

    def iterfile():
        for chunk in storage.download_chunk_stream(
            model.id, block_size=8192, model_type=model.type, compressed=compressed
        ):
            yield chunk

    # Set the appropriate filename based on the model type and compression
    if compressed:
        filename = f"{model_identifier}.{model.type}.zip"
        media_type = "application/zip"
    else:
        filename = f"{model_identifier}.{model.type}"
        media_type = "application/octet-stream"

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return StreamingResponse(iterfile(), headers=headers, media_type=media_type)

@model_router.get("/info")
def get_model_info(
    model_id: str,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Get the model information.

    Parameters:
    - model_id: str - The ID of the model to retrieve.
    - session: Session - The database session (dependency).
    - authenticated_user: AuthenticatedUser - The authenticated user (dependency).

    Returns:
    - JSONResponse: Model information.
    """
    # Fetch the model by ID
    model = session.query(schema.Model).filter_by(id=model_id).first()

    # Check if the model exists
    if not model:
        return response(
            status_code=status.HTTP_404_NOT_FOUND, message="Model not found."
        )

    result = get_high_level_model_info(model)
    return response(
        status_code=status.HTTP_200_OK,
        message="Model information retrieved successfully.",
        data=jsonable_encoder(result),
    )
