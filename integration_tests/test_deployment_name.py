import os
import uuid
from urllib.parse import urljoin

import pytest
from utils import doc_dir

pass
from client.bazaar import ModelBazaar
from client.utils import auth_header, http_get_with_error, http_post_with_error


@pytest.mark.unit
def test_deployment_name():
    base_url = "http://127.0.0.1:80/api/"

    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    model1 = admin_client.train(
        f"basic_ndb_{uuid.uuid4()}",
        unsupervised_docs=[os.path.join(doc_dir(), "articles.csv")],
        model_options={"ndb_options": {"ndb_sub_type": "v2"}},
        supervised_docs=[],
        is_async=True,
        job_options={"allocation_memory": 600},
    )

    model2 = admin_client.train(
        f"basic_ndb_{uuid.uuid4()}",
        unsupervised_docs=[os.path.join(doc_dir(), "mutual_nda.pdf")],
        model_options={"ndb_options": {"ndb_sub_type": "v2"}},
        supervised_docs=[],
        is_async=True,
    )

    admin_client.await_train(model1)
    admin_client.await_train(model2)

    deployment_name = "custom_deployment_name"

    query = "American Express Profit Rises 14"

    def test_deployment(model_identifier, expected_doc):
        client = admin_client.deploy(model_identifier, deployment_name=deployment_name)
        client.search(query)
        http_post_with_error(
            urljoin(base_url[:-4], f"{deployment_name}/search"),
            json={"query": query},
            headers=auth_header(admin_client._access_token),
        )
        source1 = http_get_with_error(
            urljoin(base_url[:-4], f"{deployment_name}/sources"),
            headers=auth_header(admin_client._access_token),
        ).json()["data"][0]["source"]

        assert os.path.basename(source1) == expected_doc

        admin_client.undeploy(client)

    test_deployment(model1.model_identifier, "articles.csv")
    test_deployment(model2.model_identifier, "mutual_nda.pdf")
