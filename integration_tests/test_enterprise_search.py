import os
import uuid
from urllib.parse import urljoin

import pytest
from thirdai import bolt
from utils import doc_dir

from client.bazaar import ModelBazaar
from client.utils import auth_header, http_post_with_error
from thirdai_platform.licensing.verify import verify_license


def upload_guardrail_model(admin_client: ModelBazaar):
    verify_license.verify_and_activate(
        os.path.join(
            os.path.dirname(__file__),
            "../thirdai_platform/tests/ndb_enterprise_license.json",
        )
    )

    model = bolt.UniversalDeepTransformer(
        data_types={
            "source": bolt.types.text(),
            "target": bolt.types.token_tags(tags=[], default_tag="O"),
        },
        target="target",
        embedding_dimension=10,
    )
    model.add_ner_rule("PHONENUMBER")

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
        model_options={},
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

    admin_client.await_deploy(client)

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


@pytest.mark.unit
def test_enterprise_search_with_constraints():
    base_url = "http://127.0.0.1:80/api/"
    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    model_name = f"basic_ndb_{uuid.uuid4()}"

    unsupervised_docs = [
        os.path.join(doc_dir(), "2023_KYI_PER.csv"),
        os.path.join(doc_dir(), "2024_MNI_PER.csv"),
    ]
    doc_options = {
        doc: {
            "csv_metadata_columns": {
                "Tax Year": "string",
                "Formset": "string",
                "Form Id": "string",
                "Table Id": "string",
                "Field ID": "string",
                "Field FullName": "string",
            }
        }
        for doc in unsupervised_docs
    }

    model = admin_client.train(
        model_name,
        unsupervised_docs=unsupervised_docs,
        model_options={},
        supervised_docs=[],
        doc_options=doc_options,
    )
    admin_client.await_train(model)

    ndb_client = admin_client.deploy(model.model_identifier)
    admin_client.await_deploy(ndb_client)

    res = ndb_client.search(
        "Account types include Checking, Savings, and Electronic for estimated tax payments",
        top_k=5,
        constraints={"Tax Year": {"constraint_type": "EqualTo", "value": "2024"}},
    )
    assert all(result["metadata"]["Formset"] == "MNI" for result in res["references"])

    res = ndb_client.search(
        "no information",
        top_k=5,
        constraints={
            "Field FullName": {"constraint_type": "Substring", "value": "CUT1"}
        },
    )
    assert all(
        result["metadata"]["Field FullName"]
        == "common-comall/pri_tool/fdiv0301.ptform:CUT1"
        for result in res["references"]
    )
