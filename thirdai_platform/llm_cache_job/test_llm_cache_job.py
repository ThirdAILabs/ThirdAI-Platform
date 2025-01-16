import glob
import os
import shutil

import pytest
from fastapi.testclient import TestClient


def auth_header(access_token):
    return {"Authorization": f"Bearer {access_token}"}


def suggestions(client, query):
    res = client.get(
        "/cache/suggestions",
        params={"query": query},
        headers=auth_header("something"),
    )
    assert res.status_code == 200

    return res.json()["suggestions"]


def query(client, query):
    res = client.get(
        "/cache/query",
        params={"query": query},
        headers=auth_header("something"),
    )
    assert res.status_code == 200

    return res.json()["cached_response"]


def try_insert(client, query, llm_res):
    return client.post(
        "/cache/insert",
        headers=auth_header("something"),
        json={"query": query, "llm_res": llm_res, "reference_ids": [0, 1, 2]},
    )


def insert(client, query, llm_res):
    assert try_insert(client, query, llm_res).status_code == 200


def dummy_verify(permission_type: str):
    def _mock_dependency(token: str = None):
        return "token"

    return _mock_dependency


@pytest.fixture(scope="function")
def temp_share():
    path = "./tmp"
    os.mkdir(path)
    yield path
    shutil.rmtree(path)


@pytest.mark.unit
def test_llm_cache(temp_share):
    os.environ["MODEL_BAZAAR_ENDPOINT"] = ""
    os.environ["MODEL_ID"] = "12345"
    os.environ["JWT_SECRET"] = "12345"
    os.environ["LLM_CACHE_THRESHOLD"] = "0.7"
    os.environ["MODEL_BAZAAR_DIR"] = temp_share
    os.environ["LICENSE_KEY"] = "236C00-47457C-4641C5-52E3BB-3D1F34-V3"

    from platform_common.permissions import Permissions

    Permissions.verify_permission = dummy_verify

    import llm_cache_job.main

    client = TestClient(llm_cache_job.main.app)

    assert len(suggestions(client, "wht is the capital of fran")) == 0

    assert query(client, "wht is the capital of fran") == None

    res = try_insert(client, "what is the capital of france", "paris")
    assert res.status_code == 200

    insert(client, "what is the capital of france", "paris")
    insert(client, "what is the capital of norway", "oslo")
    insert(
        client,
        "what is the capital of denmark",
        "coppenhagen",
    )

    pattern = os.path.join(
        temp_share,
        "models",
        os.environ["MODEL_ID"],
        "llm_cache",
        "insertions",
        "*.jsonl",
    )
    matching_files = glob.glob(pattern)
    assert len(matching_files) == 1

    with open(os.path.join(matching_files[0])) as f:
        lines = f.readlines()
        assert len(lines) == 4
        assert (
            lines[3]
            == '{"query":"what is the capital of denmark","llm_res":"coppenhagen","reference_ids":[0,1,2]}\n'
        )
