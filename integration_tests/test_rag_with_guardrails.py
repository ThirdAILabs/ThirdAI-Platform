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
def test_rag_with_guardrails():
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

    client = admin_client.deploy(model.model_identifier, memory=1500)

    query = "American Express Profit Rises 14. my phone number is 123-457-2490"
    results = client.search(query)

    assert results["query_text"] == query.replace("123-457-2490", "[PHONENUMBER #0]")

    res = http_post_with_error(
        urljoin(client.base_url, "unredact"),
        json={"text": results["query_text"], "pii_map": results["pii_map"]},
        headers=auth_header(client.login_instance.access_token),
    )
    assert res.status_code == 200

    assert res.json()["data"]["unredacted_text"] == query

    admin_client.undeploy(client)

    url = urljoin(admin_client._base_url, f"deploy/stop")
    http_post_with_error(
        url,
        params={"model_identifier": f"admin/{guardrail_name}"},
        headers=auth_header(admin_client._access_token),
    )
