import json
import os
import shutil

import pytest
import thirdai
from config import DeploymentConfig, NDBDeploymentOptions, NDBSubType
from fastapi.testclient import TestClient
from permissions import Permissions
from thirdai import neural_db as ndbv1
from thirdai import neural_db_v2 as ndbv2

MODEL_ID = "xyz"
LICENSE_KEY = "236C00-47457C-4641C5-52E3BB-3D1F34-V3"


def doc_dir():
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "train_job/sample_docs"
    )


@pytest.fixture(scope="function")
def tmp_dir():
    path = "./tmp"
    yield path
    shutil.rmtree(path)


def create_ndbv1_model(tmp_dir):
    thirdai.licensing.activate(LICENSE_KEY)

    db = ndbv1.NeuralDB()

    db.insert(
        [ndbv1.CSV(os.path.join(doc_dir(), "articles.csv"), weak_columns=["text"])]
    )

    db.save(os.path.join(tmp_dir, "models", f"{MODEL_ID}_v1", "model.ndb"))


def create_ndbv2_model(tmp_dir):
    thirdai.licensing.activate(LICENSE_KEY)

    db = ndbv2.NeuralDB()

    db.insert(
        [ndbv2.CSV(os.path.join(doc_dir(), "articles.csv"), text_columns=["text"])]
    )

    db.save(os.path.join(tmp_dir, "models", f"{MODEL_ID}_v2", "model.ndb"))


def mock_verify_permission(permission_type: str = "read"):
    return lambda: ""


def mock_check_permission(token: str, permission_type: str = "read"):
    return True


Permissions.verify_permission = mock_verify_permission
Permissions.check_permission = mock_check_permission


def create_config(tmp_dir: str, sub_type: NDBSubType, autoscaling: bool):
    if sub_type == NDBSubType.v1:
        create_ndbv1_model(tmp_dir)
    elif sub_type == NDBSubType.v2:
        create_ndbv2_model(tmp_dir)
    else:
        raise ValueError(f"Invalid subtype '{sub_type}'")

    return DeploymentConfig(
        model_id=f"{MODEL_ID}_{sub_type}",
        model_bazaar_endpoint="",
        model_bazaar_dir=tmp_dir,
        license_key=LICENSE_KEY,
        autoscaling_enabled=autoscaling,
        model_options=NDBDeploymentOptions(ndb_sub_type=sub_type),
    )


def get_query_result(client: TestClient, query: str):
    res = client.post("/predict", json={"base_params": {"query": query}})
    assert res.status_code == 200
    return res.json()["data"]["references"][0]["id"]


def check_query(client: TestClient):
    # This query corresponds to row/chunk 27 in articles.csv
    assert get_query_result(client, "manufacturing faster chips") == 27


def check_upvote_dev_mode(client: TestClient):
    random_query = "some random nonsense with no relevance to any article"
    # Here 78 is just a random chunk that we are upvoting for this query
    assert get_query_result(client, random_query) != 78

    res = client.post(
        "/upvote",
        json={"text_id_pairs": [{"query_text": random_query, "reference_id": 78}]},
    )
    assert res.status_code == 200

    assert get_query_result(client, random_query) == 78


def check_associate_dev_mode(client: TestClient):
    # This query corresponds to row/chunk 16 in articles.csv
    query = "premier league teams in england"
    assert get_query_result(client, query) != 16

    res = client.post(
        "/associate",
        json={
            "text_pairs": [
                {"source": query, "target": "man utd manchester united arsenal"}
            ]
        },
    )
    assert res.status_code == 200

    assert get_query_result(client, query) == 16


def check_insertion_dev_mode(client: TestClient):
    res = client.get("/sources")
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1
    assert res.json()["data"][0]["source"].endswith("articles.csv")

    documents = [
        {"path": "mutual_nda.pdf", "location": "local"},
        {"path": "four_english_words.docx", "location": "local"},
        {"path": "supervised.csv", "location": "local"},
    ]

    files = [
        *[
            ("files", open(os.path.join(doc_dir(), doc["path"]), "rb"))
            for doc in documents
        ],
        ("documents", (None, json.dumps({"documents": documents}), "application/json")),
    ]

    res = client.post(
        "/insert",
        files=files,
    )

    assert res.status_code == 200

    res = client.get("/sources")
    assert res.status_code == 200
    assert len(res.json()["data"]) == 4


def check_deletion_dev_mode(client: TestClient):
    res = client.get("/sources")
    assert res.status_code == 200

    source_id = [
        source["source_id"]
        for source in res.json()["data"]
        if source["source"].endswith("supervised.csv")
    ][0]

    res = client.post("/delete", json={"source_ids": [source_id]})
    assert res.status_code == 200

    res = client.get("/sources")
    assert res.status_code == 200
    assert len(res.json()["data"]) == 3


@pytest.mark.unit
@pytest.mark.parametrize("sub_type", ["v1", "v2"])
def test_deploy_ndb_dev_mode(tmp_dir, sub_type):
    from routers.ndb import NDBRouter

    config = create_config(tmp_dir=tmp_dir, sub_type=sub_type, autoscaling=False)

    router = NDBRouter(config, None)
    client = TestClient(router.router)

    check_query(client)
    check_upvote_dev_mode(client)
    check_associate_dev_mode(client)
    check_insertion_dev_mode(client)
    check_deletion_dev_mode(client)


def check_upvote_prod_mode(client: TestClient):
    random_query = "some random nonsense with no relevance to any article"
    original_result = get_query_result(client, random_query)

    # Here 78 is just a random chunk that we are upvoting for this query
    res = client.post(
        "/upvote",
        json={"text_id_pairs": [{"query_text": random_query, "reference_id": 78}]},
    )
    assert res.status_code == 202

    assert get_query_result(client, random_query) == original_result


def check_associate_prod_mode(client: TestClient):
    query = "premier league teams in england"
    orignal_result = get_query_result(client, query)

    res = client.post(
        "/associate",
        json={
            "text_pairs": [
                {"source": query, "target": "man utd manchester united arsenal"}
            ]
        },
    )
    assert res.status_code == 202

    assert get_query_result(client, query) == orignal_result


def check_insertion_prod_mode(client: TestClient):
    res = client.get("/sources")
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1
    assert res.json()["data"][0]["source"].endswith("articles.csv")

    documents = [
        {"path": "mutual_nda.pdf", "location": "local"},
        {"path": "four_english_words.docx", "location": "local"},
        {"path": "supervised.csv", "location": "local"},
    ]

    files = [
        *[
            ("files", open(os.path.join(doc_dir(), doc["path"]), "rb"))
            for doc in documents
        ],
        ("documents", (None, json.dumps({"documents": documents}), "application/json")),
    ]

    res = client.post(
        "/insert",
        files=files,
    )
    assert res.status_code == 202

    res = client.get("/sources")
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1


def check_deletion_prod_mode(client: TestClient):
    res = client.get("/sources")
    assert res.status_code == 200

    source_id = [
        source["source_id"]
        for source in res.json()["data"]
        if source["source"].endswith("articles.csv")
    ][0]

    res = client.post("/delete", json={"source_ids": [source_id]})
    assert res.status_code == 202

    res = client.get("/sources")
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1


def check_log_lines(logdir, expected_lines):
    total_lines = 0
    for logfile in os.listdir(logdir):
        if logfile.endswith(".jsonl"):
            with open(os.path.join(logdir, logfile)) as f:
                total_lines += len(f.readlines())
    assert total_lines == expected_lines


@pytest.mark.unit
@pytest.mark.parametrize("sub_type", ["v1", "v2"])
def test_deploy_ndb_prod_mode(tmp_dir, sub_type):
    from routers.ndb import NDBRouter

    config = create_config(tmp_dir=tmp_dir, sub_type=sub_type, autoscaling=True)

    router = NDBRouter(config, None)
    client = TestClient(router.router)

    deployment_dir = os.path.join(
        tmp_dir, "models", config.model_id, "deployments/data"
    )
    check_log_lines(os.path.join(deployment_dir, "feedback"), 0)
    check_log_lines(os.path.join(deployment_dir, "insertions"), 0)
    check_log_lines(os.path.join(deployment_dir, "deletions"), 0)

    check_query(client)
    check_upvote_prod_mode(client)
    check_associate_prod_mode(client)
    check_insertion_prod_mode(client)
    check_deletion_prod_mode(client)

    check_log_lines(os.path.join(deployment_dir, "feedback"), 2)
    check_log_lines(os.path.join(deployment_dir, "insertions"), 1)
    check_log_lines(os.path.join(deployment_dir, "deletions"), 1)
