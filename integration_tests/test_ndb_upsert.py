import os
import uuid

pass

import pytest

pass
from utils import doc_dir

from client.bazaar import ModelBazaar

pass


def create_and_deploy_ndb(admin_client, base_model_name, autoscaling):
    doc_path = os.path.join(doc_dir(), "articles.csv")
    base_model = admin_client.train(
        base_model_name,
        unsupervised_docs=[doc_path],
        model_options={"ndb_options": {"ndb_sub_type": "v2"}},
        supervised_docs=[],
    )
    admin_client.await_train(base_model)

    ndb_client = admin_client.deploy(
        base_model.model_identifier, autoscaling_enabled=autoscaling
    )

    old_sources = ndb_client.sources()

    ndb_client.insert(
        [
            {
                "path": doc_path,
                "location": "local",
                "doc_id": old_sources[0]["source_id"],
                "options": {"upsert": True},
            }
        ]
    )

    new_sources = ndb_client.sources()

    admin_client.undeploy(ndb_client)

    return old_sources, new_sources


@pytest.mark.unit
def test_ndb_upsert_dev_mode():
    base_url = "http://127.0.0.1:80/api/"
    doc_path = os.path.join(doc_dir(), "articles.csv")

    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    base_model_name = f"basic_ndb_{uuid.uuid4()}"

    old_sources, new_sources = create_and_deploy_ndb(
        admin_client, base_model_name, autoscaling=False
    )

    assert len(old_sources) == 1
    assert old_sources[0]["version"] == 1

    assert len(new_sources) == 1
    assert new_sources[0]["version"] == 2
    assert new_sources[0]["source_id"] == old_sources[0]["source_id"]


@pytest.mark.unit
def test_ndb_upsert_prod_mode():
    base_url = "http://127.0.0.1:80/api/"
    doc_path = os.path.join(doc_dir(), "articles.csv")

    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    base_model_name = f"basic_ndb_{uuid.uuid4()}"

    old_sources, new_sources = create_and_deploy_ndb(
        admin_client, base_model_name, autoscaling=True
    )
    assert len(old_sources) == 1
    assert old_sources[0]["version"] == 1
    assert old_sources == new_sources

    retrained_model = admin_client.retrain_ndb(
        new_model_name="retrained_" + base_model_name,
        base_model_identifier=f"admin/{base_model_name}",
    )

    ndb_client = admin_client.deploy(retrained_model.model_identifier)

    retrained_sources = ndb_client.sources()
    assert len(retrained_sources) == 1
    assert retrained_sources[0]["version"] == 2
    assert retrained_sources[0]["source_id"] == old_sources[0]["source_id"]

    admin_client.undeploy(ndb_client)
