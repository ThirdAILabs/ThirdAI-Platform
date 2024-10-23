# from unittest.mock import AsyncMock, patch

# import pytest
# from fastapi.testclient import TestClient
# from deployment_job.main import app

# from deployment_job.routers.ndb import NDBRouter

# client = TestClient(app)


# pytestmark = [pytest.mark.unit]


# @pytest.mark.parametrize("references", [[], ["Text from doc A", "Text from doc B"]])
# @pytest.mark.parametrize("prompt", [None, "This is a custom prompt"])
# def test_generate_text_stream(references, prompt):
#     async def mock_stream(*args, **kwargs):
#         yield "This "
#         yield "is "
#         yield "a test."

#     mock_llm_instance = AsyncMock()
#     mock_llm_instance.stream = mock_stream

#     with patch(
#         "deployment_job.routers.ndb.model_classes", {"openai": lambda: mock_llm_instance}
#     ):
#         request_data = {
#             "query": "test query",
#             "prompt": prompt,
#             "references": [{"text": ref, "source": "dummy.pdf"} for ref in references],
#             "provider": "openai",
#             "key": "dummy key",
#         }

#         response = client.post("/llm-dispatch/generate", json=request_data)

#         assert response.status_code == 200
#         assert response.text == "This is a test."


# def test_missing_api_key():
#     request_data = {
#         "query": "test query",
#         "provider": "openai",
#     }

#     response = client.post("/llm-dispatch/generate", json=request_data)
#     assert response.status_code == 400
#     assert response.json() == {"detail": "No generative AI key provided"}


# def test_unsupported_provider():
#     request_data = {
#         "query": "test query",
#         "provider": "unknown_provider",
#         "key": "dummy key",
#     }

#     response = client.post("/llm-dispatch/generate", json=request_data)
#     assert response.status_code == 400
#     assert response.json() == {"detail": "Unsupported provider"}


# def test_invalid_request_body():
#     request_data = {
#         # missing 'query' which is required
#         "provider": "openai",
#         "key": "dummy key",
#     }

#     response = client.post("/llm-dispatch/generate", json=request_data)
#     assert response.status_code == 422
