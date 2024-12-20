from urllib.parse import urljoin

import pytest
import requests

from client.bazaar import ModelBazaar


@pytest.mark.unit
def test_llm_dispatch_authentication():
    base_url = "http://127.0.0.1:80"

    admin_client = ModelBazaar(urljoin(base_url, "/api/"))
    admin_client.log_in("admin@mail.com", "password")

    data = {
        "query": "Hello!",
        "references": [{"text": "Some text"}],
        "key": "!",
        "provider": "openai",
    }

    headers = {"Content-Type": "application/json"}
    response = requests.post(
        urljoin(base_url, "/llm-dispatch/generate"), headers=headers, json=data
    )
    assert response.status_code == 401

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {admin_client._access_token}",
    }
    response = requests.post(
        urljoin(base_url, "/llm-dispatch/generate"), headers=headers, json=data
    )
    assert response.status_code == 200
