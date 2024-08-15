import hvac
from auth.jwt import verify_access_token
from backend.auth_dependencies import get_vault_client, global_admin_only
from backend.utils import response
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

vault_router = APIRouter()


class SecretRequest(BaseModel):
    key: str


class SecretResponse(BaseModel):
    key: str
    value: str


# Note(pratik): Only global admin can add a secret to vault
@vault_router.post(
    "/add-secret",
    dependencies=[Depends(global_admin_only)],
)
async def add_secret(
    secret: SecretResponse,
    client: hvac.Client = Depends(get_vault_client),
):
    if secret.key not in ["AWS_ACCESS_TOKEN", "OPENAI_API_KEY"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid key. Only 'AWS_ACCESS_TOKEN' and 'OPENAI_API_KEY' are allowed.",
        )
    secret_path = f"secret/data/{secret.key}"
    client.secrets.kv.v2.create_or_update_secret(
        path=secret_path, secret={"value": secret.value}
    )
    return response(
        status_code=status.HTTP_200_OK,
        message="Secret retrieved successfully",
        data={"key": secret.key, "value": secret.value},
    )


# Note(pratik): Any user can access the secrets, set by global admin
# TODO(pratik): Add a way pass the vault secrets to nomad jobs as env
# variable directly rather than accessing here
@vault_router.get("/get-secret", dependencies=[Depends(verify_access_token)])
async def get_secret(
    secret: SecretRequest, client: hvac.Client = Depends(get_vault_client)
):
    if secret.key not in [
        "AWS_ACCESS_TOKEN",
        "AWS_SECRET_ACCESS_TOKEN",
        "OPENAI_API_KEY",
    ]:
        raise HTTPException(
            status_code=400,
            detail="Invalid key. Only 'AWS_ACCESS_TOKEN', 'AWS_SECRET_ACCESS_TOKEN' and 'OPENAI_API_KEY' are allowed.",
        )
    secret_path = f"secret/data/{secret.key}"
    try:
        read_response = client.secrets.kv.v2.read_secret_version(path=secret_path)
    except hvac.exceptions.InvalidPath as e:
        return HTTPException(status_code=404, detail="Secret not found")

    secret_value = read_response["data"]["data"]["value"]
    return response(
        status_code=status.HTTP_200_OK,
        message="Secret value retrieved successfully",
        data={"key": secret.key, "value": secret_value},
    )


@vault_router.get("/list-keys", dependencies=[Depends(verify_access_token)])
async def list_vault_keys(
    client: hvac.Client = Depends(get_vault_client),
):
    try:
        list_response = client.secrets.kv.v2.list_secrets(path="secret/data/")
        keys = list_response["data"]["keys"]
        return response(
            status_code=status.HTTP_200_OK,
            message="Keys retrieved successfully",
            data={"keys": keys},
        )
    except hvac.exceptions.InvalidPath:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No keys found in the vault."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
