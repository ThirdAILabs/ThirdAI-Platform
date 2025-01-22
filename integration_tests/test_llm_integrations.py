import os
import uuid
from urllib.parse import urljoin

import pytest
import requests
from utils import doc_dir

from client.bazaar import ModelBazaar
from client.utils import auth_header, http_post_with_error

OPENAI_API_KEY = os.getenv("GENAI_KEY")
OPENAI_API_ENDPOINT = "https://api.openai.com/v1/chat/completions"


@pytest.mark.unit
def test_self_hosted_integration():
    base_url = "http://127.0.0.1:80/api/"

    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    response = admin_client.get_self_hosted_llm()
    assert response["status"] == "success"
    assert response["message"] == "No Self-Hosted LLM Integration found"

    with pytest.raises(requests.exceptions.HTTPError, match=".*400.*"):
        admin_client.set_self_hosted_llm(
            endpoint=urljoin(OPENAI_API_ENDPOINT, "/something"), api_key="bogus"
        )

    with pytest.raises(requests.exceptions.HTTPError, match=".*400.*"):
        admin_client.set_self_hosted_llm(endpoint=OPENAI_API_ENDPOINT, api_key="bogus")

    response = admin_client.set_self_hosted_llm(
        endpoint=OPENAI_API_ENDPOINT, api_key=OPENAI_API_KEY
    )
    assert response["status"] == "success"
    assert response["message"] == "Successfully set the Self-Hosted LLM Integration"

    response = admin_client.get_self_hosted_llm()
    assert response["status"] == "success"
    assert response["message"] == "Found Self-Hosted LLM Integration"
    assert response["data"]["endpoint"] == OPENAI_API_ENDPOINT
    assert response["data"]["api_key"] == OPENAI_API_KEY

    response = admin_client.delete_self_hosted_llm()
    assert response["status"] == "success"
    assert response["message"] == "Successfully deleted the Self-Hosted LLM Integration"

    response = admin_client.get_self_hosted_llm()
    assert response["status"] == "success"
    assert response["message"] == "No Self-Hosted LLM Integration found"


@pytest.mark.unit
def test_self_hosted_integration_in_models():
    base_url = "http://127.0.0.1:80/api/"

    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    response = admin_client.set_self_hosted_llm(
        endpoint=OPENAI_API_ENDPOINT, api_key=OPENAI_API_KEY
    )
    assert response["status"] == "success"
    assert response["message"] == "Successfully set the Self-Hosted LLM Integration"

    model_name = f"basic_ndb_{uuid.uuid4()}"
    model = admin_client.train(
        model_name,
        unsupervised_docs=[os.path.join(doc_dir(), "articles.csv")],
        model_options={},
        supervised_docs=[],
    )

    workflow_name = f"search_{uuid.uuid4()}"

    res = http_post_with_error(
        urljoin(admin_client._base_url, "workflow/enterprise-search"),
        headers=auth_header(admin_client._access_token),
        params={"workflow_name": workflow_name},
        json={"retrieval_id": model.model_id, "llm_provider": "self-host"},
    )

    response = admin_client.delete_self_hosted_llm()
    assert response["status"] == "success"
    assert response["message"] == "Successfully deleted the Self-Hosted LLM Integration"

    with pytest.raises(requests.exceptions.HTTPError, match=".*400.*"):
        admin_client.deploy(f"admin/{workflow_name}", memory=500)

    response = admin_client.set_self_hosted_llm(
        endpoint=OPENAI_API_ENDPOINT, api_key=OPENAI_API_KEY
    )
    assert response["status"] == "success"
    assert response["message"] == "Successfully set the Self-Hosted LLM Integration"

    client = admin_client.deploy(f"admin/{workflow_name}", memory=500)

    with pytest.raises(requests.exceptions.HTTPError, match=".*400.*"):
        response = admin_client.delete_self_hosted_llm()

    admin_client.undeploy(client)

    response = admin_client.delete_self_hosted_llm()
    assert response["status"] == "success"
    assert response["message"] == "Successfully deleted the Self-Hosted LLM Integration"
