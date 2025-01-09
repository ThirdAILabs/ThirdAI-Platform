import pathlib

import requests
from backend.auth_dependencies import global_admin_only, verify_access_token
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from platform_common.utils import response
from pydantic import BaseModel
from sqlalchemy.orm import Session

integrations_router = APIRouter()

root_folder = pathlib.Path(__file__).parent

# TODO(david) generate documentation?
# docs_file = root_folder.joinpath("../../docs/integrations_endpoints.txt")

# with open(docs_file) as f:
#     docs = f.read()

# @integrations_router.get(
#     "/llm-provider-api-key",
#     summary="Get LLM Provider API Key",
#     # description=get_section(docs, "Get LLM Provider API Key"),
#     dependencies=[Depends(verify_access_token)],
# )
# def get_llm_provider_api_key():
#     try:
#         # key key from vault
#         openai_api_key = "# openai key"
#         return {"openai_api_key": openai_api_key}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail="Failed to retrieve OpenAI API key.")


# @integrations_router.post(
#     "/llm-provider-api-key",
#     summary="Set LLM Provider API Key",
#     # description=get_section(docs, "Set LLM Provider API Key"),
#     dependencies=[Depends(global_admin_only)],
# )
# def set_llm_provider_api_key(api_key: str):
#     try:
#         # store key in vault
#         return {"message": "OpenAI API key stored successfully."}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail="Failed to store OpenAI API key.")


# @integrations_router.delete(
#     "/llm-provider-api-key",
#     summary="Delete LLM Provider API Key",
#     # description=get_section(docs, "Delete LLM Provider API Key"),
#     dependencies=[Depends(global_admin_only)],
# )
# def delete_llm_provider_api_key():
#     try:
#         # delete key from vault
#         return {"message": "OpenAI API key deleted successfully."}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail="Failed to delete OpenAI API key.")


# TODO(david): support having multiple self-hosted LLM endpoints
@integrations_router.get(
    "/self-hosted-llm",
    summary="Get Self-Hosted LLM Integration",
    # description=get_section(docs, "Get Self-Hosted LLM Integration"),
    dependencies=[Depends(verify_access_token)],
)
def get_self_hosted_llm(session: Session = Depends(get_session)):
    try:
        self_hosted_integration = (
            session.query(schema.Integrations)
            .filter_by(type=schema.IntegrationType.self_hosted)
            .first()
        )

        if self_hosted_integration is not None:
            return response(
                status_code=status.HTTP_200_OK,
                message="Found Self-Hosted LLM Integration",
                data=self_hosted_integration.data,
            )

        return response(
            status_code=status.HTTP_200_OK,
            message="No Self-Hosted LLM Integration found",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Failed to retrieve self-hosted LLM integration."
        )


def test_openai_compatible(endpoint: str, api_key: str):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Hello!"}],
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()

        json_response = response.json()
        if "choices" in json_response and isinstance(json_response["choices"], list):
            return None
        return "Error: Unexpected response structure. The endpoint may not be OpenAI-compatible."
    except requests.exceptions.HTTPError as http_err:
        if response.status_code == 401:
            return "Authentication Error: Invalid API key."
        if response.status_code == 404:
            return "Error: Endpoint not found."
    return f"Error: The endpoint may not be OpenAI-compatible."


class SelfHostedBody(BaseModel):
    endpoint: str
    api_key: str


@integrations_router.post(
    "/self-hosted-llm",
    summary="Store Self-Hosted LLM Integration",
    # description=get_section(docs, "Store Self-Hosted LLM Integration"),
    dependencies=[Depends(global_admin_only)],
)
def set_self_hosted_llm(body: SelfHostedBody, session: Session = Depends(get_session)):
    endpoint, api_key = body.endpoint, body.api_key
    failure_message = test_openai_compatible(endpoint, api_key)

    if failure_message is not None:
        raise HTTPException(status_code=400, detail=failure_message)

    try:
        existing_integration = (
            session.query(schema.Integrations)
            .filter_by(type=schema.IntegrationType.self_hosted)
            .first()
        )

        if existing_integration is not None:
            existing_integration.data = {"endpoint": endpoint, "api_key": api_key}
        else:
            self_hosted_integration = schema.Integrations(
                type=schema.IntegrationType.self_hosted,
                data={"endpoint": endpoint, "api_key": api_key},
            )
            session.add(self_hosted_integration)

        session.commit()

        return response(
            status_code=status.HTTP_200_OK,
            message="Successfully set the Self-Hosted LLM Integration",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Failed to store self-hosted LLM integration"
        )


@integrations_router.delete(
    "/self-hosted-llm",
    summary="Delete Self-Hosted LLM Integration",
    # description=get_section(docs, "Delete Self-Hosted LLM Integration"),
    dependencies=[Depends(global_admin_only)],
)
def delete_self_hosted_llm(session: Session = Depends(get_session)):
    try:
        existing_integration = (
            session.query(schema.Integrations)
            .filter_by(type=schema.IntegrationType.self_hosted)
            .first()
        )

        # TODO(david) check if any models are currently configured with the self-hosted llm and fail if they are.
        # Also, lets move towards having LLM selection at deployment time

        if existing_integration:
            session.delete(existing_integration)
            session.commit()
            return response(
                status_code=status.HTTP_200_OK,
                message="Successfully deleted the Self-Hosted LLM Integration",
            )

        return response(
            status_code=status.HTTP_200_OK,
            message="Self-Hosted LLM Integration not found",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Failed to delete self-hosted LLM integration."
        )
