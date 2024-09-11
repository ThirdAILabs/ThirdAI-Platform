import os
import shutil

import pytest
from fastapi.testclient import TestClient


def auth_header(access_token):
    return {"Authorization": f"Bearer {access_token}"}


def suggestions(client, model_id, query):
    res = client.get(
        "/cache/suggestions",
        params={"model_id": model_id, "query": query},
        headers=auth_header(""),
    )
    assert res.status_code == 200

    return res.json()["suggestions"]


def query(client, model_id, query):
    res = client.get(
        "/cache/query",
        params={"model_id": model_id, "query": query},
        headers=auth_header(""),
    )
    assert res.status_code == 200

    print(res.json())
    return res.json()["cached_response"]


def try_insert(client, query, llm_res, token):
    return client.post(
        "/cache/insert",
        headers=auth_header(token),
        params={
            "query": query,
            "llm_res": llm_res,
        },
    )


def insert(client, query, llm_res, token):
    assert try_insert(client, query, llm_res, token).status_code == 200


def get_token(client, model_id):
    res = client.get(
        "/cache/token",
        params={"model_id": model_id},
        headers=auth_header(""),
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def dummy_verify(self, model_id):
    return ""


@pytest.fixture(scope="function")
def temp_share():
    path = "./tmp"
    os.mkdir(path)
    yield path
    shutil.rmtree(path)


@pytest.mark.unit
def test_llm_cache(temp_share):
    os.environ["MODEL_BAZAAR_ENDPOINT"] = ""
    os.environ["JWT_SECRET"] = "12345"
    os.environ["LLM_CACHE_THRESHOLD"] = "0.7"
    os.environ["MODEL_BAZAAR_DIR"] = temp_share
    os.environ["LICENSE_KEY"] = "002099-64C584-3E02C8-7E51A0-DE65D9-V3"

    from permissions import Permissions

    Permissions.verify_read_permission = dummy_verify
    Permissions.verify_write_permission = dummy_verify

    import main

    client = TestClient(main.app)

    assert len(suggestions(client, "abc", "wht is the capital of fran")) == 0

    assert query(client, "abc", "wht is the capital of fran") == None

    res = try_insert(client, "what is the capital of france", "paris", token="249")
    assert res.status_code == 401

    access_token = get_token(client, "abc")

    insert(client, "what is the capital of france", "paris", access_token)
    insert(client, "what is the capital of norway", "oslo", access_token)
    insert(
        client,
        "what is the capital of denmark",
        "coppenhagen",
        get_token(client, "xyz"),
    )

    results = suggestions(client, "abc", "wht is the capital of fran")
    assert len(results) == 2
    assert results[0]["query"] == "what is the capital of france"
    assert results[1]["query"] == "what is the capital of norway"

    result = query(client, "abc", "what is the capital of franc")
    assert result["llm_res"] == "paris"

    res = client.post(
        "/cache/invalidate", params={"model_id": "abc"}, headers=auth_header("")
    )
    assert res.status_code == 200

    assert query(client, "abc", "what is the capital of franc") == None
