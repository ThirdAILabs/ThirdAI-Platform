import os
import shutil
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Setup: create a temporary directory for the model_bazaar_dir
    temp_dir = tempfile.mkdtemp()
    os.environ["MODEL_BAZAAR_DIR"] = temp_dir

    yield  # This allows the test to run after the setup

    # Teardown: remove the temporary directory after the test completes
    shutil.rmtree(temp_dir)


@pytest.mark.parametrize("references", [[], ["Text from doc A", "Text from doc B"]])
@pytest.mark.parametrize("prompt", [None, "This is a custom prompt"])
def test_generate_text_stream(references, prompt):
    from llm_dispatch_job.main import app

    client = TestClient(app)

    async def mock_stream(*args, **kwargs):
        yield "This "
        yield "is "
        yield "a test."

    mock_llm_instance = AsyncMock()
    mock_llm_instance.stream = mock_stream

    with patch(
        "llm_dispatch_job.main.model_classes", {"openai": lambda: mock_llm_instance}
    ):
        request_data = {
            "query": "test query",
            "prompt": prompt,
            "references": [{"text": ref} for ref in references],
            "provider": "openai",
            "key": "dummy key",
        }

        response = client.post("/llm-dispatch/generate", json=request_data)

        assert response.status_code == 200
        assert response.text == "This is a test."


def test_missing_api_key():
    from llm_dispatch_job.main import app

    client = TestClient(app)
    request_data = {
        "query": "test query",
        "provider": "openai",
    }

    response = client.post("/llm-dispatch/generate", json=request_data)
    assert response.status_code == 400
    assert response.json() == {"detail": "No generative AI key provided"}


def test_unsupported_provider():
    from llm_dispatch_job.main import app

    client = TestClient(app)
    request_data = {
        "query": "test query",
        "provider": "unknown_provider",
        "key": "dummy key",
    }

    response = client.post("/llm-dispatch/generate", json=request_data)
    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported provider"}


def test_invalid_request_body():
    from llm_dispatch_job.main import app

    client = TestClient(app)
    request_data = {
        # missing 'query' which is required
        "provider": "openai",
        "key": "dummy key",
    }

    response = client.post("/llm-dispatch/generate", json=request_data)
    assert response.status_code == 422


def test_health_check():
    from llm_dispatch_job.main import app

    client = TestClient(app)
    response = client.get("/llm-dispatch/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
