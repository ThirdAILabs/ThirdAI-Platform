from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


@pytest.fixture
def mock_llm_stream():
    async def mock_stream(*args, **kwargs):
        for word in ["Hello", "world!"]:
            yield word

    return mock_stream


@pytest.mark.unit
@patch(
    "main.model_classes",
    {"openai": type("MockModel", (), {"stream": mock_llm_stream})},
)
def test_generate_success(mock_llm_stream):
    payload = {"query": "Hello, world!", "provider": "openai", "key": "mock key"}
    response = client.post("/llm-dispatch/generate", json=payload)
    assert response.status_code == 200
    assert response.content == b"Hello world!"


@pytest.mark.unit
@pytest.mark.parametrize("provider", ["openai", "cohere", "on-prem"])
def test_generate_missing_key(provider):
    payload = {"query": "test query", "provider": provider}
    response = client.post("/llm-dispatch/generate", json=payload)
    assert response.status_code == 400
    assert response.json() == {"detail": "No generative AI key provided"}


@pytest.mark.unit
def test_generate_unsupported_provider():
    payload = {"query": "test query", "provider": "unsupported_provider"}
    response = client.post("/llm-dispatch/generate", json=payload)
    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported provider"}


@pytest.mark.unit
def test_health_check():
    response = client.get("/llm-dispatch/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
