import os

import hvac  # type: ignore
from auth.jwt import AuthenticatedUser, verify_access_token
from backend.utils import get_model_from_identifier
from database import schema
from database.session import get_session
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session


def get_vault_client() -> hvac.Client:
    # TODO(pratik): Change token in production environment
    # Note(pratik): Refer to the following for instruction to set up vault
    # https://waytohksharma.medium.com/install-hashicorp-vault-on-mac-fdbd8cd9113b
    """
    Initialize and return an authenticated Vault client using environment variables for the endpoint and token.

    - The `HASHICORP_VAULT_ENDPOINT` environment variable defines the Vault server URL.
      If not provided, it defaults to "http://127.0.0.1:8200".

    - The `HASHICORP_VAULT_TOKEN` environment variable provides the Vault authentication token.
      If not provided, it defaults to "00000000-0000-0000-0000-000000000000".

    Raises:
        HTTPException: If the Vault client is not authenticated.

    Returns:
        hvac.Client: An authenticated Vault client instance.
    """
    vault_url: str = os.getenv("HASHICORP_VAULT_ENDPOINT", "http://127.0.0.1:8200")
    vault_token: str = os.getenv(
        "HASHICORP_VAULT_TOKEN", "00000000-0000-0000-0000-000000000000"
    )

    client = hvac.Client(url=vault_url, token=vault_token)

    if not client.is_authenticated():
        raise HTTPException(status_code=500, detail="Vault authentication failed")

    return client


def get_current_user(
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
) -> schema.User:
    """
    Dependency to retrieve the currently authenticated user.

    Args:
        authenticated_user (AuthenticatedUser): The authenticated user returned by the JWT verification.

    Returns:
        schema.User: The authenticated user.
    """
    return authenticated_user.user


def global_admin_only(
    current_user: schema.User = Depends(get_current_user),
) -> schema.User:
    """
    Dependency to ensure the current user has global admin privileges.

    Args:
        current_user (schema.User): The currently authenticated user.

    Raises:
        HTTPException: If the user does not have global admin privileges.

    Returns:
        schema.User: The authenticated user if they have global admin privileges.
    """
    if not current_user.is_global_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user


def team_admin_or_global_admin(
    team_id: str,
    current_user: schema.User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> schema.User:
    """
    Dependency to ensure the current user has either team admin privileges for a specific team
    or global admin privileges.

    Args:
        team_id (str): The ID of the team to check admin privileges for.
        current_user (schema.User): The currently authenticated user.
        session (Session): The database session for querying the team.

    Raises:
        HTTPException: If the team is not found or the user does not have the necessary privileges.

    Returns:
        schema.User: The authenticated user if they have the required admin privileges.
    """
    team = session.query(schema.Team).filter(schema.Team.id == team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )

    if current_user.is_global_admin() or current_user.is_team_admin_of_team(team.id):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="The user doesn't have enough privileges",
    )


def is_model_owner(
    model_identifier: str,
    session: Session = Depends(get_session),
    current_user: schema.User = Depends(get_current_user),
) -> bool:
    """
    Check if the current user is the owner of the specified model.

    Args:
        model_identifier (str): The identifier of the model to check ownership for.
        session (Session): The database session for querying the model.
        current_user (schema.User): The currently authenticated user.

    Raises:
        HTTPException: If the model is not found or the user does not have owner permissions.

    Returns:
        bool: True if the user is the owner of the model.
    """
    model = get_model_from_identifier(model_identifier, session)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with identifier {model_identifier} not found",
        )

    if model.get_owner_permission(current_user):
        return True

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have owner permissions to this model",
    )


def verify_model_read_access(
    model_identifier: str,
    session: Session = Depends(get_session),
    current_user: schema.User = Depends(get_current_user),
) -> schema.Model:
    """
    Verify if the current user has read access to the specified model.

    Args:
        model_identifier (str): The identifier of the model to check read access for.
        session (Session): The database session for querying the model.
        current_user (schema.User): The currently authenticated user.

    Raises:
        HTTPException: If the model is not found or the user does not have read access.

    Returns:
        schema.Model: The model if the user has read access.
    """
    model = get_model_from_identifier(model_identifier, session)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with identifier {model_identifier} not found",
        )

    permission = model.get_user_permission(current_user)
    if permission in [schema.Permission.read, schema.Permission.write]:
        return model

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have read access to this model",
    )


def verify_model_write_access(
    model_identifier: str,
    session: Session = Depends(get_session),
    current_user: schema.User = Depends(get_current_user),
) -> schema.Model:
    """
    Verify if the current user has write access to the specified model.

    Args:
        model_identifier (str): The identifier of the model to check write access for.
        session (Session): The database session for querying the model.
        current_user (schema.User): The currently authenticated user.

    Raises:
        HTTPException: If the model is not found or the user does not have write access.

    Returns:
        schema.Model: The model if the user has write access.
    """
    model = get_model_from_identifier(model_identifier, session)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with identifier {model_identifier} not found",
        )

    permission = model.get_user_permission(current_user)
    if permission == schema.Permission.write:
        return model

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have write access to this model",
    )
