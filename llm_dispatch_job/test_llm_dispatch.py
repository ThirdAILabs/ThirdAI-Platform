import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


pytestmark = [pytest.mark.unit]


@pytest.mark.asyncio
async def test_generate_text_stream():
    async def mock_stream(*args, **kwargs):
        yield "This "
        yield "is "
        yield "a test."

    mock_llm_instance = AsyncMock()
    mock_llm_instance.stream = mock_stream

    with patch("main.model_classes", {"openai": lambda: mock_llm_instance}):
        request_data = {
            "query": "test query",
            "provider": "openai",
            "key": "dummy key",
        }

        response = client.post("/llm-dispatch/generate", json=request_data)

        assert response.status_code == 200
        assert response.text == "This is a test."


def test_health_check():
    response = client.get("/llm-dispatch/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
