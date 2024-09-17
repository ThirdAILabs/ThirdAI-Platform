import os
import uuid
from urllib.parse import urljoin

import pytest
import requests

from client.bazaar import Model, ModelBazaar
from client.utils import auth_header, create_model_identifier


def doc_dir():
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "train_job/sample_docs/"
    )


@pytest.mark.unit
def test_ndb_retraining_log_feedback_from_read_only_users():
    base_url = "http://127.0.0.1:80/api/"

    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    base_model_name = f"basic_ndb_{uuid.uuid4()}"
    base_model = admin_client.train(
        base_model_name,
        unsupervised_docs=[os.path.join(doc_dir(), "articles.csv")],
        model_options={"ndb_options": {"ndb_sub_type": "v2"}},
        supervised_docs=[],
    )
    admin_client.await_train(base_model)

    ndb_client = admin_client.deploy(base_model.model_identifier)
    admin_client.await_deploy(ndb_client)

    res = requests.post(
        urljoin(base_url, "model/update-access-level"),
        params={
            "model_identifier": ndb_client.model_identifier,
            "access_level": "public",
        },
        headers=auth_header(admin_client._access_token),
    )
    assert res.status_code == 200

    username = str(uuid.uuid4())
    user_email = f"{username}@mail.com"
    user_client = ModelBazaar(base_url)
    user_client.sign_up(email=user_email, password="password1", username=username)
    user_client.log_in(email=user_email, password="password1")

    ndb_client.login_instance = user_client._login_instance

    ndb_client.associate([{"source": "my source query", "target": "my target query"}])
    ndb_client.upvote([{"query_text": "a query to upvote", "reference_id": 0}])

    res = requests.post(
        urljoin(ndb_client.base_url, "implicit-feedback"),
        json={
            "query_text": "query to a clicked reference",
            "reference_id": 1,
            "event_desc": "reference click",
        },
        headers=auth_header(ndb_client.login_instance.access_token),
    )
    assert res.status_code == 200

    res = ndb_client.search("a query to upvote", top_k=1)
    assert res["references"][0]["id"] != 0

    admin_client.undeploy(ndb_client)

    retrained_model_name = "retrained_" + base_model_name
    res = requests.post(
        urljoin(admin_client._base_url, "train/ndb-retrain"),
        params={
            "model_name": retrained_model_name,
            "base_model_identifier": ndb_client.model_identifier,
        },
        headers=auth_header(admin_client._access_token),
    )
    assert res.status_code == 200

    retrained_model = Model(
        model_identifier=create_model_identifier(
            model_name=retrained_model_name, author_username=admin_client._username
        ),
        model_id=res.json()["data"]["model_id"],
    )

    admin_client.await_train(retrained_model)

    ndb_client.login_instance = admin_client._login_instance

    ndb_client = admin_client.deploy(retrained_model.model_identifier)
    admin_client.await_deploy(ndb_client)

    res = ndb_client.search("a query to upvote", top_k=1)
    assert res["references"][0]["id"] == 0

    admin_client.undeploy(ndb_client)


@pytest.mark.unit
def test_ndb_retraining_autoscaling_mode():
    base_url = "http://127.0.0.1:80/api/"

    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    base_model_name = f"basic_ndb_{uuid.uuid4()}"
    base_model = admin_client.train(
        base_model_name,
        unsupervised_docs=[
            os.path.join(doc_dir(), "articles.csv"),
            os.path.join(doc_dir(), "supervised.csv"),
        ],
        model_options={"ndb_options": {"ndb_sub_type": "v2"}},
        supervised_docs=[],
    )
    admin_client.await_train(base_model)

    ndb_client = admin_client.deploy(
        base_model.model_identifier, autoscaling_enabled=True
    )
    admin_client.await_deploy(ndb_client)

    ndb_client.associate([{"source": "my source query", "target": "my target query"}])
    ndb_client.upvote([{"query_text": "a query to upvote", "reference_id": 0}])

    ndb_client.insert(
        [
            {
                "path": os.path.join(doc_dir(), "mutual_nda.pdf"),
                "location": "local",
            },
            {
                "path": os.path.join(doc_dir(), "four_english_words.docx"),
                "location": "local",
            },
        ]
    )

    res = ndb_client.search("a query to upvote", top_k=1)
    assert res["references"][0]["id"] != 0

    sources = ndb_client.sources()
    assert len(sources) == 2

    sources_to_remove = [
        s["source_id"] for s in sources if s["source"].endswith("supervised.csv")
    ]
    assert len(sources_to_remove) == 1
    ndb_client.delete(sources_to_remove)

    assert len(ndb_client.sources()) == 2

    admin_client.undeploy(ndb_client)

    retrained_model = admin_client.retrain_ndb(
        new_model_name="retrained_" + base_model_name,
        base_model_identifier=ndb_client.model_identifier,
    )

    ndb_client = admin_client.deploy(retrained_model.model_identifier)
    admin_client.await_deploy(ndb_client)

    sources = ndb_client.sources()
    assert len(sources) == 3

    source_names = [os.path.split(source["source"])[-1] for source in sources]
    expected_sources = ["articles.csv", "mutual_nda.pdf", "four_english_words.docx"]
    assert set(source_names) == set(expected_sources)

    res = ndb_client.search("a query to upvote", top_k=1)
    assert res["references"][0]["id"] == 0

    admin_client.undeploy(ndb_client)
