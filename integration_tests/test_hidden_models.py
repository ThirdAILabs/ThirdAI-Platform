import os
import uuid
from urllib.parse import urljoin

import pytest
from utils import doc_dir

from client.bazaar import ModelBazaar
from client.utils import auth_header, http_post_with_error


@pytest.mark.unit
def test_hidden_model_management():
    base_url = "http://127.0.0.1:80/api/"

    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    model_name = f"basic_ndb_{uuid.uuid4()}"
    model = admin_client.train(
        model_name,
        unsupervised_docs=[os.path.join(doc_dir(), "articles.csv")],
        model_options={"ndb_options": {"ndb_sub_type": "v2"}},
        supervised_docs=[],
        hidden=True,
    )

    workflow_name = f"search_{uuid.uuid4()}"

    def model_names(ignore_hidden):
        return [m["model_name"] for m in admin_client.list_models(ignore_hidden)]

    assert model_name in model_names(ignore_hidden=False)
    assert model_name not in model_names(ignore_hidden=True)

    http_post_with_error(
        urljoin(admin_client._base_url, "workflow/enterprise-search"),
        headers=auth_header(admin_client._access_token),
        params={"workflow_name": workflow_name},
        json={"retrieval_id": model.model_id},
    )
    workflow = f"admin/{workflow_name}"

    client = admin_client.deploy(workflow, memory=500)

    assert admin_client.deploy_status(workflow)["deploy_status"] == "complete"
    assert (
        admin_client.deploy_status(model.model_identifier)["deploy_status"]
        == "complete"
    )

    admin_client.undeploy(client)

    # Check that hidden model is stopped
    assert admin_client.deploy_status(workflow)["deploy_status"] == "stopped"
    assert (
        admin_client.deploy_status(model.model_identifier)["deploy_status"] == "stopped"
    )

    admin_client.delete(workflow)

    # Check that hidden model is deleted
    assert model_name not in model_names(ignore_hidden=False)
    assert model_name not in model_names(ignore_hidden=True)
