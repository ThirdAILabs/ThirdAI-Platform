import json
import os
import uuid
from typing import Annotated, Dict, Optional, Union

from auth.jwt import AuthenticatedUser, verify_access_token
from backend.auth_dependencies import (
    global_admin_only,
    is_model_owner,
    team_admin_or_global_admin,
    verify_model_read_access,
    verify_model_read_access_from_id,
)
from backend.utils import (
    delete_nomad_job,
    get_expiry_min,
    get_high_level_model_info,
    get_model,
    get_model_from_identifier,
    model_bazaar_path,
    validate_name,
)
from database import schema
from database.session import get_session
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, StreamingResponse
from platform_common.utils import response
from pydantic import BaseModel
from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session, joinedload, selectinload
from storage import interface, local

model_router = APIRouter()

storage: interface.StorageInterface = local.LocalStorage(model_bazaar_path())


@model_router.get("/details")
def get_model_details(
    model_id: str,
    model: schema.Model = Depends(verify_model_read_access_from_id),
):

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully retrieved model details.",
        data=jsonable_encoder(get_high_level_model_info(model)),
    )


@model_router.get("/list")
def list_models(
    name: Optional[str] = None,
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
    user_teams = [ut.team_id for ut in user.teams]

    query = (
        session.query(schema.Model)
        .options(
            joinedload(schema.Model.user),
            selectinload(schema.Model.attributes),
            selectinload(schema.Model.dependencies),
            selectinload(schema.Model.used_by),
        )
        .order_by(desc(schema.Model.published_date))
    )

    if name:
        query.filter(schema.Model.name.ilike(f"%{name}%"))

    if not user.is_global_admin():
        access_conditions = [
            session.query(schema.ModelPermission)
            .where(
                and_(
                    schema.ModelPermission.model_id == schema.Model.id,
                    schema.ModelPermission.user_id == user.id,
                )
            )
            .exists(),
        ]

        def add_access_condition(access: schema.Access, condition):
            if not access_level or access.value in access_level:
                access_conditions.append(condition)

        # Adding access conditions based on the user's role and teams
        add_access_condition(
            schema.Access.public, schema.Model.access_level == schema.Access.public
        )
        add_access_condition(
            schema.Access.protected,
            and_(
                schema.Model.access_level == schema.Access.protected,
                schema.Model.team_id.in_(user_teams),
            ),
        )
        add_access_condition(
            schema.Access.private,
            and_(
                schema.Model.access_level == schema.Access.private,
                schema.Model.user_id == user.id,
            ),
        )

        query = query.filter(or_(*access_conditions))

    if domain:
        query = query.filter(schema.Model.domain == domain)

    if username:
        query = query.join(schema.User).filter(schema.User.username == username)

    if type:
        query = query.filter(schema.Model.type == type)

    if sub_type:
        query = query.filter(schema.Model.sub_type == sub_type)

    results = [get_high_level_model_info(result) for result in query]

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully retrieved model list",
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
    model_exists = (
        session.query(schema.Model)
        .filter(and_(schema.Model.name == name, schema.Model.user_id == user.id))
        .first()
    )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully checked for model name",
        data={"model_present": model_exists is not None},
    )


class SaveNDBDeployedModel(BaseModel):
    model_id: str
    base_model_id: str
    model_name: str
    metadata: Dict[str, str]

    class Config:
        protected_namespaces = ()


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

    new_model = schema.Model(
        id=body.model_id,
        name=body.model_name,
        train_status=schema.Status.complete,
        deploy_status=schema.Status.not_started,
        access_level=schema.Access.private,
        domain=user.domain,
        user_id=user.id,
        parent_id=base_model.id,
        type=base_model.type,
        sub_type=base_model.sub_type,
    )

    session.add(new_model)

    for dependency in base_model.dependencies:
        session.add(
            schema.ModelDependency(
                model_id=body.model_id, dependency_id=dependency.dependency_id
            )
        )

    for attribute in base_model.attributes:
        session.add(
            schema.ModelAttribute(
                model_id=body.model_id, key=attribute.key, value=attribute.value
            )
        )

    session.commit()
    session.refresh(new_model)

    metadata: schema.MetaData = schema.MetaData(
        model_id=body.model_id, general=body.metadata
    )

    session.add(metadata)
    session.commit()

    return {"message": "Successfully added the model."}


class ModelInfo(BaseModel):
    type: str
    sub_type: Optional[str] = None
    access_level: schema.Access = "public"
    metadata: Optional[Dict[str, str]] = None


@model_router.get("/upload-token")
def upload_token(
    model_name: str,
    size: int,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Generates a token for uploading a model to the platform.

    Parameters:
    - model_name: str - The name that the uploaded model will take in the platform.
        Example: "my_new_model"
    - size: int - The size of the model to be uploaded.
        Example: 150

    Returns:
    - JSONResponse: A token, which is used to upload chunks of a model.
    """
    user: schema.User = authenticated_user.user
    try:
        validate_name(model_name)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    model_exists = get_model(session, username=user.username, model_name=model_name)

    if model_exists:
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
        message="Successfully got the upload token",
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
    Uploads a chunk of a model.

    Parameters:
    - chunk: UploadFile - The raw bytes of the chunk.
        Example: UploadFile(file=BytesIO(b"chunk data"), filename="chunk1.zip")
    - chunk_number: int - The position of the chunk of the model that is being uploaded.
        Example: 1
    - model_type: str - The type of model being uploaded (default: "ndb").
        Example: "ndb"
    - compressed: bool - Whether the chunk is compressed (default: True).
        Example: True
    - authorization: str - Bearer token that contains the token generated from /upload-token.
        Example: "Bearer <token>"

    Returns:
    - JSONResponse: Success message if the chunk is uploaded successfully.
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
            model_id=payload["model_id"],
            chunk_data=chunk_data,
            chunk_number=chunk_number,
            model_type=model_type,
            compressed=compressed,
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


@model_router.post("/upload-commit")
def upload_commit(
    total_chunks: int,
    body: ModelInfo,
    compressed: bool = True,
    authorization: str = Header(None),
    session: Session = Depends(get_session),
):
    """
    Commits the upload of a model after all chunks have been uploaded.

    Parameters:
    - total_chunks: int - The total number of chunks uploaded.
        Example: 10
    - body: ModelInfo - The information about the model being uploaded.
        Example:
        ```
        {
            "type": "ndb",
            "sub_type": "subtype_example",
            "access_level": "public",
            "metadata": {
                "key1": "value1",
                "key2": "value2"
            }
        }
        ```
    - authorization: str - Bearer token that contains the token generated from /upload-token.
        Example: "Bearer <token>"

    Returns:
    - JSONResponse: Success message if the model upload is committed successfully.
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

    model_name = payload["model_identifier"].split("/")[1]
    model_exists = (
        session.query(schema.Model)
        .filter(
            schema.Model.user_id == payload["user_id"], schema.Model.name == model_name
        )
        .first()
    )

    if model_exists:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"There is already a model saved with {model_name}",
        )

    try:
        storage.commit_upload(
            model_id=payload["model_id"],
            total_chunks=total_chunks,
            model_type=body.type,
            compressed=compressed,
        )
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    user: schema.User = session.query(schema.User).get(payload["user_id"])

    try:
        new_model = schema.Model(
            id=payload["model_id"],
            name=model_name,
            access_level=body.access_level,
            type=body.type,
            sub_type=body.sub_type,
            domain=user.domain,
            user_id=payload["user_id"],
            train_status=schema.Status.complete,
            deploy_status=schema.Status.not_started,
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
            general=json.dumps(body.metadata),
        )
        session.add(new_metadata)
        session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="Committed model",
        data={"model_id": str(new_model.id)},
    )


@model_router.get("/public-download")
def download_public_model(
    model_identifier: str,
    session: Session = Depends(get_session),
):
    """
    Downloads specified public model. No login required.

    Parameters:
    - model_identifier: str - The model identifier of the model to be downloaded.
        Example: "user123/my_model"

    Returns:
    - StreamingResponse: Streams the download of the model to the caller.
    """
    try:
        model: schema.Model = get_model_from_identifier(model_identifier, session)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    if model.access_level != schema.Access.public:
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
    filename = (
        f"{model_identifier}.{model.type}.zip"
        if compressed
        else f"{model_identifier}.{model.type}"
    )
    media_type = "application/zip" if compressed else "application/octet-stream"

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return StreamingResponse(iterfile(), headers=headers, media_type=media_type)


@model_router.get("/download", dependencies=[Depends(verify_model_read_access)])
def download_model(
    model_identifier: str,
    session: Session = Depends(get_session),
):
    """
    Downloads specified model.

    Parameters:
    - model_identifier: str - The model identifier of the model to be downloaded.
        Example: "user123/my_model"

    Returns:
    - StreamingResponse: Streams the download of the model to the caller.
    """
    try:
        model: schema.Model = get_model_from_identifier(model_identifier, session)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
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
    filename = (
        f"{model_identifier}.{model.type}.zip"
        if compressed
        else f"{model_identifier}.{model.type}"
    )
    media_type = "application/zip" if compressed else "application/octet-stream"

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return StreamingResponse(iterfile(), headers=headers, media_type=media_type)


@model_router.get("/team-models", dependencies=[Depends(team_admin_or_global_admin)])
def list_team_models(
    team_id: str,
    session: Session = Depends(get_session),
):
    """
    List all models associated with a specific team.

    Parameters:
    - team_id: The ID of the team.
    - session: The database session (dependency).

    Returns:
    - A JSON response with the list of team models.
    """
    team = session.query(schema.Team).get(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )

    results = (
        session.query(schema.Model)
        .filter(schema.Model.team_id == team.id)
        .options(
            joinedload(schema.Model.user),
            selectinload(schema.Model.attributes),
            selectinload(schema.Model.dependencies),
            selectinload(schema.Model.used_by),
        )
        .all()
    )

    results = [get_high_level_model_info(result) for result in results]

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the team models list",
        data=jsonable_encoder(results),
    )


@model_router.post("/update-model-permission", dependencies=[Depends(is_model_owner)])
def update_model_permission(
    model_identifier: str,
    email: str,
    permission: schema.Permission,
    session: Session = Depends(get_session),
):
    """
    Update a user's permission for a specific model.

    Parameters:
    - model_identifier: The identifier of the model.
    - email: The email of the user whose permission is being updated.
    - permission: The new permission to assign to the user.
    - session: The database session (dependency).

    Returns:
    - A JSON response indicating the success of the operation.
    """
    model = get_model_from_identifier(model_identifier, session)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with identifier {model_identifier} not found",
        )
    user = session.query(schema.User).filter(schema.User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    existing_permission = model.get_user_permission(user)
    if existing_permission and existing_permission == permission:
        return response(
            status_code=status.HTTP_200_OK,
            message=f"User already has this permission.",
        )

    model_permission = (
        session.query(schema.ModelPermission)
        .filter_by(model_id=model.id, user_id=user.id)
        .first()
    )

    if model_permission:
        model_permission.permission = permission
    else:
        new_permission = schema.ModelPermission(
            model_id=model.id, user_id=user.id, permission=permission
        )
        session.add(new_permission)

    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message=f"Permission updated to '{permission}' for user '{email}' on model '{model_identifier}'.",
        data={"model_id": str(model.id), "user_id": str(user.id)},
    )


@model_router.get("/all-models", dependencies=[Depends(global_admin_only)])
def list_all_models(
    session: Session = Depends(get_session),
):
    """
    List all models in the system.

    Parameters:
    - session: The database session (dependency).

    Returns:
    - A JSON response with the list of all models.
    """
    results = session.query(schema.Model).all()

    results = [get_high_level_model_info(result) for result in results]

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the list of all models",
        data=jsonable_encoder(results),
    )


def deduplicate_permissions(permissions_list: list[dict]) -> list[dict]:
    """
    Remove duplicates from a list of permissions, where each permission is a dictionary.
    """
    return [dict(t) for t in {tuple(d.items()) for d in permissions_list}]


@model_router.get("/permissions", dependencies=[Depends(is_model_owner)])
def get_model_permissions(
    model_identifier: str,
    session: Session = Depends(get_session),
):
    """
    Get detailed information about users' permissions on a specific model.

    Parameters:
    - model_identifier: The identifier of the model to retrieve permissions for.
    - session: The database session (dependency).

    Returns:
    - A JSON response with the list of users and their permissions on the model.
    """
    model = get_model_from_identifier(model_identifier, session)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model not found"
        )

    permissions_info = {"owner": [], "write": [], "read": []}

    # Adding model owner and global admins as owners
    owner = session.query(schema.User).filter(schema.User.id == model.user_id).first()
    if owner:
        permissions_info["owner"].append(
            {"user_id": owner.id, "username": owner.username, "email": owner.email}
        )

    global_admins = (
        session.query(schema.User).filter(schema.User.global_admin == True).all()
    )
    for admin in global_admins:
        permissions_info["owner"].append(
            {"user_id": admin.id, "username": admin.username, "email": admin.email}
        )

    explicit_permissions = (
        session.query(schema.ModelPermission)
        .join(schema.User)
        .filter(schema.ModelPermission.model_id == model.id)
        .all()
    )

    for perm in explicit_permissions:
        if perm.permission == schema.Permission.write:
            permissions_info["write"].append(
                {
                    "user_id": perm.user.id,
                    "username": perm.user.username,
                    "email": perm.user.email,
                }
            )
        elif perm.permission == schema.Permission.read:
            permissions_info["read"].append(
                {
                    "user_id": perm.user.id,
                    "username": perm.user.username,
                    "email": perm.user.email,
                }
            )

    # Team permissions for protected models
    if model.access_level == schema.Access.protected:
        team_users = (
            session.query(schema.UserTeam)
            .join(schema.User)
            .filter(schema.UserTeam.team_id == model.team_id)
            .all()
        )
        for user_team in team_users:
            if user_team.role == schema.Role.team_admin:
                permissions_info["owner"].append(
                    {
                        "user_id": user_team.user.id,
                        "username": user_team.user.username,
                        "email": user_team.user.email,
                    }
                )
            permission = model.get_user_permission(user_team.user)
            permissions_info[str(permission).split(".")[-1]].append(
                {
                    "user_id": user_team.user.id,
                    "username": user_team.user.username,
                    "email": user_team.user.email,
                }
            )

    # Deduplicate all permission lists
    permissions_info = {
        key: deduplicate_permissions(value) for key, value in permissions_info.items()
    }

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully retrieved model permissions",
        data=jsonable_encoder(permissions_info),
    )


@model_router.post("/update-access-level", dependencies=[Depends(is_model_owner)])
def update_access_level(
    model_identifier: str,
    access_level: schema.Access,
    team_id: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """
    Update the access level of a model.

    Parameters:
    - model_identifier: The identifier of the model to update.
    - access_level: The new access level to set for the model.

    Returns:
    - A JSON response indicating the success of the operation, including the model ID and the updated access level.
    """
    model = get_model_from_identifier(model_identifier, session)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    if access_level == schema.Access.protected:
        if not team_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="team_id is required when setting access level to 'protected'.",
            )

        # Check if the provided team_id is valid
        team = session.query(schema.Team).get(team_id)
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The provided team_id does not exist.",
            )

        # Assign the team_id to the model
        model.team_id = team_id

    model.access_level = access_level
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message=f"Access level updated to '{access_level}' for model '{model_identifier}'.",
        data={"model_id": str(model.id), "access_level": str(model.access_level)},
    )


@model_router.post("/update-default-permission", dependencies=[Depends(is_model_owner)])
def update_default_permission(
    model_identifier: str,
    new_permission: schema.Permission,
    session: Session = Depends(get_session),
):
    """
    Update the default permission of a model.

    Parameters:
    - model_identifier: The identifier of the model to update.
    - new_permission: The new default permission to set.

    Returns:
    - A JSON response indicating the success of the operation, including the model ID and the updated default permission.
    """
    model = get_model_from_identifier(model_identifier, session)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Directly update the default permission
    model.default_permission = new_permission
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message=f"Default permission updated to '{new_permission}' for model '{model_identifier}'.",
        data={
            "model_id": str(model.id),
            "default_permission": str(model.default_permission),
        },
    )


@model_router.post("/delete", dependencies=[Depends(is_model_owner)])
def delete_model(
    model_identifier: str,
    session: Session = Depends(get_session),
):
    """
    Deletes a specified model.

    - **model_identifier**: The model identifier of the model to delete
    """

    try:
        model: schema.Model = get_model_from_identifier(model_identifier, session)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    if len(model.used_by) > 0:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Cannot delete model '{model_identifier}' since it is used in other workflows.",
        )

    errors = []

    # Step 1: Delete model storage
    try:
        storage.delete(model.id)
    except Exception as storage_error:
        errors.append(f"Failed to delete model from storage: {str(storage_error)}")

    # Step 2: Delete Nomad job
    try:
        delete_nomad_job(f"deployment-{model.id}", os.getenv("NOMAD_ENDPOINT"))
    except Exception as nomad_error:
        errors.append(f"Failed to delete Nomad job: {str(nomad_error)}")

    # Step 3: Delete model from the database
    try:
        session.delete(model)
        session.commit()
    except Exception as db_error:
        errors.append(f"Failed to delete model from database: {str(db_error)}")

    # If any errors occurred, return them in the response
    if errors:
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Model deletion encountered issues.",
            data={"errors": errors},
        )

    return response(
        status_code=status.HTTP_200_OK, message="Successfully deleted the model."
    )


@model_router.get("/logs", dependencies=[Depends(is_model_owner)])
def get_model_logs(
    model_identifier: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    Get the logs for a specified model and provide them as a downloadable zip file.
    The zip file will be deleted after being sent to the client.

    Parameters:
    - model_identifier: str - The identifier of the model to retrieve logs for.

    Returns:
    - FileResponse: A zip file containing the model logs, which will be deleted after sending.
    """
    try:
        # Retrieve the model from the database
        model: schema.Model = get_model_from_identifier(model_identifier, session)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    # Fetch the logs from the storage system and zip them
    try:
        zip_filepath = storage.logs(model.id)
    except Exception as error:
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Error zipping logs: {str(error)}",
        )

    # Schedule the deletion of the zip file after the response is completed
    background_tasks.add_task(os.remove, zip_filepath)

    # Return the zip file as a downloadable file
    return FileResponse(
        path=zip_filepath,
        media_type="application/zip",
        filename=f"{model_identifier}_logs.zip",
    )
