import datetime
import os
import secrets
from threading import Lock
from typing import Dict, List, Tuple
from urllib.parse import urljoin

import fastapi
import jwt
import requests
from fastapi import status
from pydantic import BaseModel

CREDENTIALS_EXCEPTION = fastapi.HTTPException(
    status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
    detail="Invalid access token.",
    # This header indicates what type of authentication would be required to access
    # the resource.
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/WWW-Authenticate
    headers={"WWW-Authenticate": "Bearer"},
)


class TokenPayload(BaseModel):
    model_id: str
    exp: datetime.datetime


def optional_token_bearer(request: fastapi.Request) -> str:
    """
    Retrieves the token from the Authorization header if it exists, otherwise returns "None".
    """
    # Attempt to retrieve the Authorization header from the request,
    # and return "None" for token if header doesn't exist.
    auth_header = request.headers.get("Authorization")
    if auth_header:
        try:
            # Extract the token type and the token itself from the header.
            token_type, token = auth_header.split(" ", 1)
            if token_type.lower() == "bearer":
                return token
        except ValueError:
            # Return "None" as a dummy value for the token,
            # since we need some string value for the token permission verification.
            return "None"
    return "None"


def now() -> datetime.datetime:
    """
    Returns the current UTC time without microseconds.
    """
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def deployment_permissions(model_bazaar_endpoint: str, model_id: str, token: str):
    deployment_permissions_endpoint = urljoin(
        model_bazaar_endpoint, f"api/deploy/permissions/{model_id}"
    )
    response = requests.get(
        deployment_permissions_endpoint,
        headers={"Authorization": "Bearer " + token},
    )
    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        return {
            "read": False,
            "write": False,
            "exp": now() + datetime.timedelta(minutes=5),
            "override": False,
        }
    elif response.status_code != status.HTTP_200_OK:
        return {
            "read": False,
            "write": False,
            "exp": now(),
            "override": False,
        }
    res_json = response.json()
    permissions = res_json["data"]
    permissions["exp"] = datetime.datetime.fromisoformat(permissions["exp"])
    return permissions


class Permissions:
    def __init__(self, entry_expiration_min: int = 5):
        """
        Manages permissions for tokens with caching and expiration.

        Args:
            entry_expiration_min (int): Number of minutes until the permissions
                                        for a token need to be refreshed.
        """
        # entry_expiration_seconds: number of seconds until the permissions for a
        # token needs to be refreshed. We refresh in case a previously invalid
        # token becomes a valid token.
        self.model_bazaar_endpoint = os.environ["MODEL_BAZAAR_ENDPOINT"]
        self.entry_expiration_min = entry_expiration_min
        self.expirations: List[Tuple[datetime.datetime, str]] = []
        self.cache: Dict[str, dict] = {}
        self.cache_lock = Lock()

        # Because these secrets are just used temporary authentication for cache insertions
        # and have a short expiration, we just generate a secure random token on startup to
        # avoid having to pass the JWT secret to the nomad job running this caching service.
        self.secret = secrets.SystemRandom().randbytes(16)

    def _clear_expired_entries(self) -> None:
        """
        Clears expired entries from the cache.
        """
        pos = 0
        curr_time = now()
        for expiration, token in self.expirations:
            if expiration > curr_time:
                break
            try:
                del self.cache[token]
            except KeyError:
                pass
            pos += 1
        self.expirations = self.expirations[pos:]

    def _get_permissions(self, model_id: str, token: str) -> Tuple[bool, bool, bool]:
        """
        Retrieves permissions for a token, updating the cache if necessary.

        Args:
            token (str): The access token.

        Returns:
            Tuple[bool, bool, bool]: Read, write, and override permissions.
        """
        self._clear_expired_entries()
        curr_time = now()
        if token not in self.cache:
            permissions = deployment_permissions(
                model_bazaar_endpoint=self.model_bazaar_endpoint,
                model_id=model_id,
                token=token,
            )
            self.expirations.append(
                (
                    curr_time + datetime.timedelta(minutes=self.entry_expiration_min),
                    token,
                )
            )
            self.cache[token] = permissions
            return permissions["read"], permissions["write"], permissions["override"]
        if self.cache[token]["exp"] <= curr_time:
            return False, False, False
        permissions = self.cache[token]
        return permissions["read"], permissions["write"], permissions["override"]

    def verify_read_permission(
        self, model_id: str, token: str = fastapi.Depends(optional_token_bearer)
    ) -> str:
        """
        Verifies read permission for the token.

        Args:
            token (str): The access token.

        Returns:
            str: The access token if permission is granted.

        Raises:
            HTTPException: If the token does not have read permission.
        """
        with self.cache_lock:
            if not self._get_permissions(model_id=model_id, token=token)[0]:
                raise CREDENTIALS_EXCEPTION
        return token

    def verify_write_permission(
        self, model_id: str, token: str = fastapi.Depends(optional_token_bearer)
    ) -> str:
        """
        Verifies write permission for the token.

        Args:
            token (str): The access token.

        Returns:
            str: The access token if permission is granted.

        Raises:
            HTTPException: If the token does not have write permission.
        """
        with self.cache_lock:
            if not self._get_permissions(model_id=model_id, token=token)[1]:
                raise CREDENTIALS_EXCEPTION
        return token

    def create_temporary_cache_access_token(self, model_id: str) -> str:
        """
        We need to pass some sort of access token to /generate so that the generation
        service can update the cache. However headers cannot be passed to a json WebSocket,
        and url params are less secure. Thus we don't want to use the regular auth token.
        This method creates a temporary access token that has a short expiration and
        can only be used to update the llm cache. The user must request that token and
        then pass it to /generate so that the generation service can update the cache.
        """
        payload = {
            "exp": datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=3),
            "model_id": model_id,
        }

        return jwt.encode(payload=payload, key=self.secret, algorithm="HS256")

    def verify_temporary_cache_access_token(
        self, token: str = fastapi.Depends(optional_token_bearer)
    ):
        try:
            payload = TokenPayload(
                **jwt.decode(token, key=self.secret, algorithms=["HS256"])
            )
            if payload.model_id is None:
                raise CREDENTIALS_EXCEPTION

            return payload.model_id
        except jwt.PyJWTError:
            raise CREDENTIALS_EXCEPTION
