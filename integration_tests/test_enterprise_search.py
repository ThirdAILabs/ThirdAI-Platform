import os
import uuid
from urllib.parse import urljoin

import pytest
from thirdai import bolt, licensing
from utils import doc_dir

from client.bazaar import ModelBazaar
from client.utils import auth_header, http_post_with_error


def upload_guardrail_model(admin_client: ModelBazaar):
    licensing.activate("236C00-47457C-4641C5-52E3BB-3D1F34-V3")

    model = bolt.UniversalDeepTransformer(
        data_types={
            "source": bolt.types.text(),
            "target": bolt.types.token_tags(tags=["PHONENUMBER"], default_tag="O"),
        },
        target="target",
        rules=True,
        embedding_dimension=10,
    )

    path = "./phone_guardrail"
    model.save(path)

    name = f"basic_guardrail_{uuid.uuid4()}"
    model_id = admin_client.upload_model(
        local_path=path,
        model_name=name,
        model_type="udt",
        model_subtype="token",
    )["model_id"]

    os.remove(path)

    return name, model_id


@pytest.mark.unit
def test_enterprise_search_with_guardrails():
    base_url = "http://127.0.0.1:80/api/"

    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    guardrail_name, guardrail_id = upload_guardrail_model(admin_client)

    model_name = f"basic_ndb_{uuid.uuid4()}"
    model = admin_client.train(
        model_name,
        unsupervised_docs=[os.path.join(doc_dir(), "articles.csv")],
        model_options={
            "ndb_options": {"ndb_sub_type": "v2"},
            "rag_options": {"guardrail_model_id": guardrail_id},
        },
        supervised_docs=[],
    )

    workflow_name = f"search_{uuid.uuid4()}"

    res = http_post_with_error(
        urljoin(admin_client._base_url, "workflow/enterprise-search"),
        headers=auth_header(admin_client._access_token),
        params={"workflow_name": workflow_name},
        json={"retrieval_id": model.model_id, "guardrail_id": guardrail_id},
    )

    client = admin_client.deploy(f"admin/{workflow_name}", memory=500)

    es_deps = admin_client.model_details(client.model_id)["dependencies"]
    assert len(es_deps) == 2
    assert set(m["model_id"] for m in es_deps) == set([guardrail_id, model.model_id])
    assert set(m["model_name"] for m in es_deps) == set(
        [guardrail_name, model.model_identifier.split("/")[1]]
    )

    ndb_used_by = admin_client.model_details(model.model_id)["used_by"]
    assert len(ndb_used_by) == 1
    assert [m["model_id"] for m in ndb_used_by] == [client.model_id]
    assert [m["model_name"] for m in ndb_used_by] == [
        client.model_identifier.split("/")[1]
    ]

    query = "American Express Profit Rises 14. my phone number is 123-457-2490"
    results = client.search(query)
    assert results["query_text"] == query.replace("123-457-2490", "[PHONENUMBER#0]")

    res = http_post_with_error(
        urljoin(client.base_url, "unredact"),
        json={"text": results["query_text"], "pii_entities": results["pii_entities"]},
        headers=auth_header(client.login_instance.access_token),
    )
    assert res.json()["data"]["unredacted_text"] == query

    admin_client.undeploy(client)

    http_post_with_error(
        urljoin(admin_client._base_url, f"deploy/stop"),
        params={"model_identifier": model.model_identifier},
        headers=auth_header(admin_client._access_token),
    )

    http_post_with_error(
        urljoin(admin_client._base_url, f"deploy/stop"),
        params={"model_identifier": f"admin/{guardrail_name}"},
        headers=auth_header(admin_client._access_token),
    )
