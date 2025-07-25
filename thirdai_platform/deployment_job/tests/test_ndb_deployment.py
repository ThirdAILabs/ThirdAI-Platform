import json
import math
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import List, Optional
from unittest.mock import patch

import pytest
from deployment_job.permissions import Permissions
from fastapi.testclient import TestClient
from licensing.verify import verify_license
from platform_common.logging import JobLogger
from platform_common.pydantic_models.deployment import (
    DeploymentConfig,
    NDBDeploymentOptions,
)
from thirdai import neural_db_v2 as ndbv2
from thirdai.neural_db_v2.chunk_stores import PandasChunkStore
from thirdai.neural_db_v2.retrievers import FinetunableRetriever

DEPLOYMENT_ID = "123"
USER_ID = "abc"
MODEL_ID = "xyz"

THIRDAI_LICENSE = os.path.join(
    os.path.dirname(__file__), "../../tests/ndb_enterprise_license.json"
)


logger = JobLogger(
    log_dir=Path("./tmp"),
    log_prefix="deployment",
    service_type="deployment",
    model_id="model-123",
    model_type="ndb",
    user_id="user-123",
)


def doc_dir():
    return os.path.join(os.path.dirname(__file__), "../../train_job/sample_docs")


@pytest.fixture(scope="function")
def tmp_dir():
    path = "./tmp"
    os.environ["SHARE_DIR"] = path
    os.makedirs(path, exist_ok=True)
    yield path
    shutil.rmtree(path)


def create_ndbv2_model(
    tmp_dir: str,
    on_disk: bool,
    doc_path: str,
    text_columns: Optional[List[str]] = None,
    keyword_columns: Optional[List[str]] = None,
):
    verify_license.verify_and_activate(THIRDAI_LICENSE)

    random_path = f"{uuid.uuid4()}.ndb"

    if on_disk:
        db = ndbv2.NeuralDB(save_path=random_path)
    else:
        db = ndbv2.NeuralDB(
            chunk_store=PandasChunkStore(),
            retriever=FinetunableRetriever(random_path),
        )

    db.insert(
        [
            ndbv2.CSV(
                doc_path, text_columns=text_columns, keyword_columns=keyword_columns
            )
        ]
    )

    db.save(os.path.join(tmp_dir, "models", f"{MODEL_ID}", "model.ndb"))
    db.save(
        os.path.join(
            tmp_dir,
            "host_dir",
            "models",
            f"{MODEL_ID}",
            f"{DEPLOYMENT_ID}",
            "model.ndb",
        )
    )

    shutil.rmtree(random_path)


def mock_verify_permission(permission_type: str = "read"):
    return lambda: ""


def mock_check_permission(token: str, permission_type: str = "read"):
    return True


def create_config(
    tmp_dir: str,
    autoscaling: bool,
    on_disk: bool,
    doc_path: str,
    text_columns: Optional[List[str]] = None,
    keyword_columns: Optional[List[str]] = None,
):
    create_ndbv2_model(tmp_dir, on_disk, doc_path, text_columns, keyword_columns)

    license_info = verify_license.verify_license(THIRDAI_LICENSE)

    return DeploymentConfig(
        deployment_id=DEPLOYMENT_ID,
        user_id=USER_ID,
        model_id=MODEL_ID,
        model_bazaar_endpoint="",
        model_bazaar_dir=tmp_dir,
        host_dir=os.path.join(tmp_dir, "host_dir"),
        license_key=license_info["boltLicenseKey"],
        autoscaling_enabled=autoscaling,
        model_options=NDBDeploymentOptions(
            llm_provider="openai", genai_key="random_key"
        ),
    )


def get_query_result(
    client: TestClient, query: str, top_k: int, constraints: dict = {}
):
    res = client.post(
        "/search", json={"query": query, "top_k": top_k, "constraints": constraints}
    )
    assert res.status_code == 200
    return res.json()["data"]


def check_query(
    client: TestClient,
    query: str,
    top_k: int,
    ref0_chunk_id: int,
    constraints: dict = {},
):
    assert (
        get_query_result(client, query, top_k=top_k, constraints=constraints)[
            "references"
        ][0]["id"]
        == ref0_chunk_id
    )


def check_upvote_dev_mode(client: TestClient):
    random_query = "some random nonsense with no relevance to any article"
    # Here 78 is just a random chunk that we are upvoting for this query
    assert get_query_result(client, random_query, top_k=5)["references"][0]["id"] != 78

    res = client.post(
        "/upvote",
        json={
            "text_id_pairs": [
                {
                    "query_text": random_query,
                    "reference_id": 78,
                    "reference_text": "This is the corresponding reference text.",
                }
            ]
        },
    )
    assert res.status_code == 200

    assert get_query_result(client, random_query, top_k=5)["references"][0]["id"] == 78


def check_associate_dev_mode(client: TestClient):
    # This query corresponds to row/chunk 16 in articles.csv
    query = "premier league teams in england"
    assert get_query_result(client, query, top_k=5)["references"][0]["id"] != 16

    res = client.post(
        "/associate",
        json={
            "text_pairs": [
                {"source": query, "target": "man utd manchester united arsenal"}
            ]
        },
    )
    assert res.status_code == 200

    assert get_query_result(client, query, top_k=5)["references"][0]["id"] == 16


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


def check_async_insertion_dev_mode(client: TestClient):
    res = client.get("/sources")
    assert res.status_code == 200

    documents = [
        {
            "path": "apple-10k.pdf",
            "location": "local",
            "source_id": "async_insertion_doc",
        },
    ]

    files = [
        *[
            ("files", open(os.path.join(doc_dir(), doc["path"]), "rb"))
            for doc in documents
        ],
        ("documents", (None, json.dumps({"documents": documents}), "application/json")),
    ]

    res = client.post(
        "/insert?sync=False",
        files=files,
    )
    assert res.status_code == 202

    task_id = res.json()["data"]["task_id"]
    res = client.get(
        "/tasks",
    )
    all_tasks = res.json()["data"]["tasks"]
    assert task_id in all_tasks

    num_seconds = 30
    for i in range(num_seconds):
        res = client.get(
            f"/tasks?task_id={task_id}",
        )
        task_info = res.json()["data"]["task"]
        if task_info["status"] == "complete":
            break
        time.sleep(1)
    else:
        raise RuntimeError(
            f"Async insertion did not complete after {num_seconds} seconds"
        )

    res = client.get("/sources")
    assert res.status_code == 200

    source_ids = [s["source_id"] for s in res.json()["data"]]
    assert "async_insertion_doc" in source_ids


def check_async_deletion_dev_mode(client: TestClient):
    res = client.get("/sources")
    assert res.status_code == 200

    source_ids = [s["source_id"] for s in res.json()["data"]]
    assert "async_insertion_doc" in source_ids

    res = client.post(
        "/delete?sync=False", json={"source_ids": ["async_insertion_doc"]}
    )
    assert res.status_code == 202

    task_id = res.json()["data"]["task_id"]
    res = client.get(
        "/tasks",
    )
    all_tasks = res.json()["data"]["tasks"]
    assert task_id in all_tasks

    num_seconds = 30
    for i in range(num_seconds):
        res = client.get(
            f"/tasks?task_id={task_id}",
        )
        task_info = res.json()["data"]["task"]
        if task_info["status"] == "complete":
            break
        time.sleep(1)
    else:
        raise RuntimeError(
            f"Async deletion did not complete after {num_seconds} seconds"
        )

    res = client.get("/sources")
    assert res.status_code == 200

    source_ids = [s["source_id"] for s in res.json()["data"]]
    assert "async_insertion_doc" not in source_ids


@pytest.mark.unit
@patch.object(Permissions, "verify_permission", mock_verify_permission)
@patch.object(Permissions, "check_permission", mock_check_permission)
def test_deploy_ndb_dev_mode(tmp_dir):
    from deployment_job.routers.ndb import NDBRouter

    config = create_config(
        tmp_dir=tmp_dir,
        autoscaling=False,
        on_disk=True,
        doc_path=os.path.join(doc_dir(), "articles.csv"),
        text_columns=["text"],
    )

    router = NDBRouter(config, None, logger)
    client = TestClient(router.router)

    check_query(
        client, query="manufacturing faster chips", top_k=5, ref0_chunk_id=27
    )  # This query corresponds to row/chunk 27 in articles.csv
    check_upvote_dev_mode(client)
    check_associate_dev_mode(client)
    check_insertion_dev_mode(client)
    check_deletion_dev_mode(client)
    check_async_insertion_dev_mode(client)
    check_async_deletion_dev_mode(client)


def check_upvote_prod_mode(client: TestClient):
    random_query = "some random nonsense with no relevance to any article"
    original_result = get_query_result(client, random_query, top_k=5)["references"][0][
        "id"
    ]

    # Here 78 is just a random chunk that we are upvoting for this query
    res = client.post(
        "/upvote",
        json={
            "text_id_pairs": [
                {
                    "query_text": random_query,
                    "reference_id": 78,
                    "reference_text": "This is the corresponding reference text.",
                }
            ]
        },
    )
    assert res.status_code == 202

    assert (
        get_query_result(client, random_query, top_k=5)["references"][0]["id"]
        == original_result
    )


def check_associate_prod_mode(client: TestClient):
    query = "premier league teams in england"
    orignal_result = get_query_result(client, query, top_k=5)["references"][0]["id"]

    res = client.post(
        "/associate",
        json={
            "text_pairs": [
                {"source": query, "target": "man utd manchester united arsenal"}
            ]
        },
    )
    assert res.status_code == 202

    assert (
        get_query_result(client, query, top_k=5)["references"][0]["id"]
        == orignal_result
    )


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
@pytest.mark.parametrize("on_disk", [True, False])
@patch.object(Permissions, "verify_permission", mock_verify_permission)
@patch.object(Permissions, "check_permission", mock_check_permission)
def test_deploy_ndb_prod_mode(tmp_dir, on_disk):
    from deployment_job.routers.ndb import NDBRouter

    config = create_config(
        tmp_dir=tmp_dir,
        autoscaling=True,
        on_disk=on_disk,
        doc_path=os.path.join(doc_dir(), "articles.csv"),
        text_columns=["text"],
    )

    router = NDBRouter(config, None, logger)
    client = TestClient(router.router)

    deployment_dir = os.path.join(
        tmp_dir, "models", config.model_id, "deployments/data"
    )
    check_log_lines(os.path.join(deployment_dir, "feedback"), 0)
    check_log_lines(os.path.join(deployment_dir, "insertions"), 0)
    check_log_lines(os.path.join(deployment_dir, "deletions"), 0)

    check_query(
        client, query="manufacturing faster chips", top_k=5, ref0_chunk_id=27
    )  # This query corresponds to row/chunk 27 in articles.csv
    check_upvote_prod_mode(client)
    check_associate_prod_mode(client)
    check_insertion_prod_mode(client)
    check_deletion_prod_mode(client)

    check_log_lines(os.path.join(deployment_dir, "feedback"), 2)
    check_log_lines(os.path.join(deployment_dir, "insertions"), 1)
    check_log_lines(os.path.join(deployment_dir, "deletions"), 1)


def check_summarized_metadata(client: TestClient):
    res = client.get("/sources")
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1
    assert res.json()["data"][0]["source"].endswith("metadata_doc.csv")
    met_res = client.get(
        "/get-metadata",
        params={
            "source_id": res.json()["data"][0]["source_id"],
            "version": res.json()["data"][0]["version"],
        },
    )

    data = met_res.json()["data"]
    assert data["integer_col"]["min"] == -200
    assert data["integer_col"]["max"] == 188

    # Assert float col
    assert math.isclose(data["float_col"]["min"], -198.06391226887988, rel_tol=1e-6)
    assert math.isclose(data["float_col"]["max"], 198.34493105274356, rel_tol=1e-6)

    # Assert string col
    assert set(data["string_col"]["unique_values"]) == set(
        [
            "grape",
            "honeydew",
            "apple",
            "lemon",
            "cherry",
            "banana",
            "date",
            "fig",
            "elderberry",
            "kiwi",
        ]
    )

    # Assert bool col
    assert set(data["bool_col"]["unique_values"]) == set([True, False])


@pytest.mark.unit
@pytest.mark.parametrize("on_disk", [True, False])
@patch.object(Permissions, "verify_permission", mock_verify_permission)
@patch.object(Permissions, "check_permission", mock_check_permission)
def test_deployment_constrained_search(tmp_dir, on_disk):
    from deployment_job.routers.ndb import NDBRouter

    config = create_config(
        tmp_dir=tmp_dir,
        autoscaling=True,
        on_disk=on_disk,
        doc_path=os.path.join(doc_dir(), "metadata_doc.csv"),
        text_columns=["text"],
        keyword_columns=["keywords"],
    )

    router = NDBRouter(config, None, logger)
    client = TestClient(router.router)

    # Get the summarized metadata
    check_summarized_metadata(client)

    # check the results of the constrained search
    check_query(
        client,
        query="Velit magnam labore numquam ipsum.",
        top_k=5,
        ref0_chunk_id=30,
        constraints={
            "integer_col": {
                "constraint_type": "InRange",
                "min_value": -10,
                "max_value": 10,
            }
        },
    )

    check_query(
        client,
        query="Velit magnam labore numquam ipsum.",
        top_k=5,
        ref0_chunk_id=7,
        constraints={
            "float_col": {
                "constraint_type": "InRange",
                "min_value": -80.56,
                "max_value": -75.456,
            }
        },
    )

    check_query(
        client,
        query="Velit magnam labore numquam ipsum.",
        top_k=5,
        ref0_chunk_id=85,
        constraints={
            "string_col": {
                "constraint_type": "AnyOf",
                "values": ["lemon", "elderberry"],
            },
            "bool_col": {"constraint_type": "EqualTo", "value": True},
        },
    )
