from fastapi.testclient import TestClient
import os
import pytest


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


def insert(client, model_id, query, llm_res):
    res = client.post(
        "/cache/insert",
        headers=auth_header(""),
        params={
            "model_id": model_id,
            "query": query,
            "llm_res": llm_res,
        },
    )
    assert res.status_code == 200


def dummy_verify(self, model_id):
    return ""


@pytest.mark.unit
def test_llm_cache():
    os.environ["MODEL_BAZAAR_ENDPOINT"] = ""
    from permissions import Permissions

    Permissions.verify_read_permission = dummy_verify

    import main

    client = TestClient(main.app)

    assert len(suggestions(client, "abc", "wht is the capital of fran")) == 0

    assert query(client, "abc", "wht is the capital of fran") == None

    insert(client, "abc", "what is the capital of france", "paris")
    insert(client, "abc", "what is the capital of norway", "oslo")
    insert(client, "xyz", "what is the capital of denmark", "coppenhagen")

    results = suggestions(client, "abc", "wht is the capital of fran")
    assert len(results) == 2
    assert results[0]["query"] == "what is the capital of france"
    assert results[1]["query"] == "what is the capital of norway"

    result = query(client, "abc", "what is the capital of franc")
    assert result["llm_res"] == "paris"
