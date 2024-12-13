from typing import Literal, Optional, Union

import hvac  # type: ignore
from auth.jwt import verify_access_token
from backend.auth_dependencies import get_vault_client, global_admin_only
from fastapi import APIRouter, Depends, HTTPException, status
from platform_common.pydantic_models.cloud_credentials import (
    AWSCredentials,
    AzureCredentials,
    GCPCredentials,
    GenericKeyValue,
)
from platform_common.utils import response
from pydantic import BaseModel

vault_router = APIRouter()


# Main model using Union to select the right type based on provided data
class SecretRequest(BaseModel):
    cloud_type: Optional[Literal["aws", "azure", "gcp", "generic"]] = "generic"
    level: Optional[Literal["global", "bucket"]] = None
    identifier: Optional[str] = None
    credentials: Union[
        AWSCredentials, AzureCredentials, GCPCredentials, GenericKeyValue
    ]

    @property
    def path(self):
        """Determine the Vault path based on cloud_type and level."""
        if self.cloud_type == "generic":
            return f"secret/data/generic/{self.identifier}"
        elif self.level == "global":
            return f"secret/data/{self.cloud_type}/global"
        elif self.level == "bucket" and self.identifier:
            return f"secret/data/{self.cloud_type}/bucket/{self.identifier}"
        else:
            raise ValueError(
                "Invalid configuration: bucket-level credentials require an identifier."
            )


@vault_router.post(
    "/store-secret",
    dependencies=[Depends(global_admin_only)],
)
async def store_secret(
    secret_request: SecretRequest, client: hvac.Client = Depends(get_vault_client)
):
    # Use the path property to determine where to store the credentials
    path = secret_request.path

    # Store validated credentials or key-value pair in Vault
    client.secrets.kv.v2.create_or_update_secret(
        path=path, secret=secret_request.credentials.model_dump()
    )

    return response(
        status_code=status.HTTP_200_OK, message=f"Secret stored successfully at {path}"
    )


@vault_router.get(
    "/retrieve-secret",
    dependencies=[Depends(verify_access_token)],
)
async def retrieve_secret(
    cloud_type: Literal["generic", "aws", "azure", "gcp"],
    level: Optional[Literal["global", "bucket"]] = None,
    identifier: Optional[str] = None,
    client: hvac.Client = Depends(get_vault_client),
):
    # Determine path for retrieval
    if cloud_type == "generic":
        path = f"secret/data/generic/{identifier}"
    elif level == "global":
        path = f"secret/data/{cloud_type}/global"
    elif level == "bucket" and identifier:
        path = f"secret/data/{cloud_type}/bucket/{identifier}"
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid configuration: bucket-level credentials require an identifier.",
        )

    try:
        read_response = client.secrets.kv.v2.read_secret_version(path=path)
        secret_data = read_response["data"]["data"]
    except hvac.exceptions.InvalidPath:
        raise HTTPException(
            status_code=404, detail=f"Secret not found at path '{path}'"
        )

    return response(
        status_code=status.HTTP_200_OK,
        message=f"Successfully retrieved secret from {path}",
        data={"path": path, "data": secret_data},
    )


@vault_router.get(
    "/list-all-secrets",
    dependencies=[Depends(verify_access_token)],
)
async def list_all_secrets(client: hvac.Client = Depends(get_vault_client)):
    all_secrets = {}

    # Define the top-level paths for each category of secrets
    base_paths = {
        "generic": "secret/data/generic",
        "aws_global": "secret/data/aws/global",
        "aws_buckets": "secret/data/aws/bucket",
        "azure_global": "secret/data/azure/global",
        "azure_buckets": "secret/data/azure/bucket",
        "gcp_global": "secret/data/gcp/global",
        "gcp_buckets": "secret/data/gcp/bucket",
    }

    # Helper function to list secrets at a specific path
    def list_secrets_at_path(path):
        try:
            return (
                client.secrets.kv.v2.list_secrets(path=path)
                .get("data", {})
                .get("keys", [])
            )
        except hvac.exceptions.InvalidPath:
            return []
        except hvac.exceptions.Forbidden:
            raise HTTPException(
                status_code=403, detail=f"Permission denied to access path '{path}'."
            )

    # Retrieve secrets for each path and organize them
    for label, path in base_paths.items():
        if "bucket" in label:
            # Special case for bucket paths to get all bucket-specific keys
            bucket_names = list_secrets_at_path(path)
            all_secrets[label] = {}
            for bucket in bucket_names:
                bucket_path = f"{path}/{bucket}"
                all_secrets[label][bucket] = list_secrets_at_path(bucket_path)
        else:
            # Global or generic paths
            all_secrets[label] = list_secrets_at_path(path)

    return response(
        status_code=status.HTTP_200_OK,
        message=f"Successfully listed all secrets",
        data={"all_secrets": all_secrets},
    )
