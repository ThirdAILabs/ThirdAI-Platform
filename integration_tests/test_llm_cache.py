import glob
import os
import time
import uuid

import pytest
import requests

from client.bazaar import ModelBazaar
from integration_tests.utils import doc_dir


def wait_for_cache(cache_health_url, action):
    for _ in range(20):
        res = requests.get(cache_health_url)
        if action == "start" and res.status_code == 200:
            return
        if action == "stop" and res.status_code != 200:
            return
        time.sleep(1)
    raise ValueError("cache job not stopped in expected time")


def wait_for_cache_refresh(cache_status_url, model_identifier, auth_header):
    for _ in range(20):
        res = requests.get(
            cache_status_url,
            params={"model_identifier": model_identifier},
            headers=auth_header,
        )
        if (
            res.status_code == 200
            and res.json()["data"]["cache_refresh_status"] == "complete"
        ):
            return
        time.sleep(1)
    raise ValueError("cache job not refreshed in expected time")


@pytest.mark.unit
def test_llm_cache():
    base_url = "http://127.0.0.1:80/api/"

    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    base_model_name = f"basic_ndb_{uuid.uuid4()}"
    base_model = admin_client.train(
        base_model_name,
        unsupervised_docs=[os.path.join(doc_dir(), "articles.csv")],
        supervised_docs=[],
    )

    ndb_client = admin_client.deploy(
        base_model.model_identifier, autoscaling_enabled=True
    )

    def auth_header():
        return {
            "Authorization": f"Bearer {admin_client._access_token}",
        }

    model_id = base_model.model_id
    model_identifier = base_model.model_identifier

    cache_health_url = f"http://127.0.0.1:80/{model_id}/cache/health"

    wait_for_cache(cache_health_url, action="start")

    model_bazaar_dir = os.getenv("SHARE_DIR")
    cache_file_path = os.path.join(
        model_bazaar_dir, "models", model_id, "llm_cache", "llm_cache.ndb"
    )
    assert os.path.exists(cache_file_path)

    # test authentication
    suggestions_url = f"http://127.0.0.1:80/{model_id}/cache/suggestions"
    suggestions_response = requests.get(
        suggestions_url,
        params={"query": "lol"},
        headers={"Authorization": "Bearer faulty_token"},
    )
    assert suggestions_response.status_code == 401

    suggestions_response = requests.get(
        suggestions_url,
        params={"query": "lol"},
        headers=auth_header(),
    )
    assert suggestions_response.status_code == 200
    assert len(suggestions_response.json()["suggestions"]) == 0

    # a query which should be evicted on retraining
    insertion_url = f"http://127.0.0.1:80/{model_id}/cache/insert"
    insertion_response = requests.post(
        insertion_url,
        json={"query": "lol", "llm_res": "response", "reference_ids": [0]},
        headers=auth_header(),
    )
    assert insertion_response.status_code == 200

    # a query which should not be evicted on retraining
    res = ndb_client.search("Toronto", top_k=5)
    toronto_ref_ids = [ref["id"] for ref in res["references"]]
    insertion_response = requests.post(
        insertion_url,
        json={
            "query": "Toronto",
            "llm_res": "response",
            "reference_ids": toronto_ref_ids,
        },
        headers=auth_header(),
    )
    assert insertion_response.status_code == 200

    pattern = os.path.join(
        model_bazaar_dir,
        "models",
        model_id,
        "llm_cache",
        "insertions",
        "new",
        "*.jsonl",
    )
    matching_files = glob.glob(pattern)
    assert len(matching_files) == 1

    ndb_client.insert(
        [
            {
                "path": os.path.join(doc_dir(), "mutual_nda.pdf"),
                "location": "local",
            },
        ]
    )

    admin_client.undeploy(ndb_client)
    wait_for_cache(cache_health_url, action="stop")

    cache_status_url = f"{base_url}train/cache-status"
    response = requests.get(
        cache_status_url,
        params={"model_identifier": model_identifier},
        headers=auth_header(),
    )
    assert response.status_code == 200
    assert response.json()["data"]["cache_refresh_status"] == "not_started"

    refresh_url = f"{base_url}train/refresh-llm-cache"
    refresh_response = requests.post(
        refresh_url,
        params={"model_identifier": base_model.model_identifier},
        headers=auth_header(),
    )
    assert refresh_response.status_code == 200

    wait_for_cache_refresh(cache_status_url, model_identifier, auth_header())

    pattern = os.path.join(
        model_bazaar_dir,
        "models",
        model_id,
        "llm_cache",
        "insertions",
        "new",
        "*.jsonl",
    )
    matching_files = glob.glob(pattern)
    assert len(matching_files) == 0
    assert os.path.exists(
        os.path.join(
            model_bazaar_dir,
            "models",
            model_id,
            "llm_cache",
            "insertions",
            "past_insertions.jsonl",
        )
    )

    ndb_client = admin_client.deploy(
        base_model.model_identifier, autoscaling_enabled=True
    )

    wait_for_cache(cache_health_url, action="start")

    suggestions_response_after_restart = requests.get(
        suggestions_url,
        params={"query": "lol"},
        headers=auth_header(),
    )
    assert suggestions_response_after_restart.status_code == 200
    assert len(suggestions_response_after_restart.json()["suggestions"]) == 1

    admin_client.undeploy(ndb_client)

    retrained_model = admin_client.retrain_ndb(
        new_model_name="retrained5_" + base_model_name,
        base_model_identifier=ndb_client.model_identifier,
    )

    evicted_responses_file = os.path.join(
        model_bazaar_dir,
        "models",
        retrained_model.model_id,
        "llm_cache",
        "insertions",
        "evicted_responses.jsonl",
    )
    assert os.path.exists(evicted_responses_file)
    with open(evicted_responses_file, "r") as f:
        assert len(f.readlines()) == 1

    ndb_client = admin_client.deploy(
        retrained_model.model_identifier, autoscaling_enabled=True
    )

    sources = ndb_client.sources()
    assert len(sources) == 2

    suggestions_url = (
        f"http://127.0.0.1:80/{retrained_model.model_id}/cache/suggestions"
    )
    suggestions_response_after_restart = requests.get(
        suggestions_url,
        params={"query": "lol"},
        headers=auth_header(),
    )
    assert suggestions_response_after_restart.status_code == 200
    assert len(suggestions_response_after_restart.json()["suggestions"]) == 0

    suggestions_response_after_restart = requests.get(
        suggestions_url,
        params={"query": "Toronto"},
        headers=auth_header(),
    )
    assert suggestions_response_after_restart.status_code == 200
    assert len(suggestions_response_after_restart.json()["suggestions"]) == 1

    admin_client.undeploy(ndb_client)
