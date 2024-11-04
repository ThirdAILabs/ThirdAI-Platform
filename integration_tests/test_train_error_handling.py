import uuid
from urllib.parse import urljoin

import pytest

from client.bazaar import ModelBazaar
from client.utils import auth_header, http_get_with_error


@pytest.mark.unit
def test_train_error_handling():
    base_url = "http://127.0.0.1:80/api/"

    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    model_name = f"basic_ndb_{uuid.uuid4()}"
    model = admin_client.train(
        model_name,
        unsupervised_docs=[__file__],
        model_options={
            "ndb_options": {"ndb_sub_type": "v2"},
        },
        supervised_docs=[],
        is_async=True,
    )

    with pytest.raises(ValueError, match=f"Training Failed for admin/{model_name}"):
        admin_client.await_train(model)

    status_info = admin_client.train_status(model)

    error = ".py Document type isn't supported"
    assert error in status_info["messages"][0]

    res = http_get_with_error(
        urljoin(admin_client._base_url, "train/logs"),
        params={"model_identifier": model.model_identifier},
        headers=auth_header(admin_client._access_token),
    )

    assert error in res.json()["data"][0]["stderr"]
