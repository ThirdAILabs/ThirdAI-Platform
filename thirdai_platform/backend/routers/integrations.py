import pathlib

import requests
from backend.auth_dependencies import global_admin_only, verify_access_token
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from platform_common.utils import get_section, response
from pydantic import BaseModel
from sqlalchemy.orm import Session

integrations_router = APIRouter()

root_folder = pathlib.Path(__file__).parent

docs_file = root_folder.joinpath("../../docs/integrations_endpoints.txt")

with open(docs_file) as f:
    docs = f.read()


# TODO(david): support having multiple self-hosted LLM endpoints
# TODO(david): move endpoints/api keys to vault
@integrations_router.get(
    "/self-hosted-llm",
    summary="Get Self-Hosted LLM Integration",
    description=get_section(docs, "Get Self-Hosted LLM Integration"),
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
    description=get_section(docs, "Store Self-Hosted LLM Integration"),
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
    description=get_section(docs, "Delete Self-Hosted LLM Integration"),
    dependencies=[Depends(global_admin_only)],
)
def delete_self_hosted_llm(session: Session = Depends(get_session)):
    try:
        existing_integration = (
            session.query(schema.Integrations)
            .filter_by(type=schema.IntegrationType.self_hosted)
            .first()
        )

        # TODO(david) can we move towards having LLM selection be more dynamic vs
        # being rigidly attached to the model
        models = (
            session.query(schema.Model)
            .join(schema.ModelAttribute)
            .filter(
                schema.ModelAttribute.key == "llm_provider",
                schema.ModelAttribute.value == "self-host",
            )
            .all()
        )

        for model in models:
            if model.deploy_status == schema.Status.complete:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete self-hosted integration if there are existing deployments using it.",
                )

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
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Failed to delete self-hosted LLM integration."
        )
