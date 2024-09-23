import datetime
from threading import Lock
from typing import Callable, Dict, List, Tuple
from urllib.parse import urljoin

import fastapi
import requests
from fastapi import status

CREDENTIALS_EXCEPTION = fastapi.HTTPException(
    status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
    detail="Invalid access token.",
    # This header indicates what type of authentication would be required to access
    # the resource.
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/WWW-Authenticate
    headers={"WWW-Authenticate": "Bearer"},
)


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


class Permissions:
    def __init__(
        self, model_bazaar_endpoint: str, model_id: str, entry_expiration_min: int = 5
    ):
        """
        Manages permissions for tokens with caching and expiration.

        Args:
            entry_expiration_min (int): Number of minutes until the permissions
                                        for a token need to be refreshed.
        """
        self.model_bazaar_endpoint = model_bazaar_endpoint
        self.model_id = model_id
        # entry_expiration_seconds: number of seconds until the permissions for a
        # token needs to be refreshed. We refresh in case a previously invalid
        # token becomes a valid token.
        self.entry_expiration_min = entry_expiration_min
        self.expirations: List[Tuple[datetime.datetime, str]] = []
        self.cache: Dict[str, dict] = {}
        self.cache_lock = Lock()

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

    def _deployment_permissions(self, token: str):
        deployment_permissions_endpoint = urljoin(
            self.model_bazaar_endpoint,
            f"api/deploy/permissions/{self.model_id}",
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
            print(response.text)
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

    def _get_permissions(self, token: str) -> Tuple[bool, bool, bool]:
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
            permissions = self._deployment_permissions(token)
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

    def verify_permission(self, permission_type: str = "read") -> Callable[[str], str]:
        """
        Creates a function that verifies a specific permission type for the token.

        Args:
            permission_type (str): The type of permission to verify (read, write, override).

        Returns:
            Callable: A function that takes the token and checks the permission.
        """

        def dependency(token: str = fastapi.Depends(optional_token_bearer)) -> str:
            with self.cache_lock:
                permissions = self._get_permissions(token)
                permission_map = {
                    "read": permissions[0],
                    "write": permissions[1],
                    "override": permissions[2],
                }
                if not permission_map.get(permission_type):
                    raise CREDENTIALS_EXCEPTION
                return token

        return dependency

    def check_permission(self, token: str, permission_type: str = "read") -> bool:
        """
        Checks if a specific permission type is granted for the token.

        Args:
            token (str): The access token.
            permission_type (str): The type of permission to check (read, write, override).

        Returns:
            bool: True if the token has the required permission, False otherwise.
        """
        with self.cache_lock:
            permissions = self._get_permissions(token)
            permission_map = {
                "read": permissions[0],
                "write": permissions[1],
                "override": permissions[2],
            }
            return permission_map.get(permission_type, False)
