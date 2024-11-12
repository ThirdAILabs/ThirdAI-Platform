import os
import shutil
import uuid
from urllib.parse import urljoin

import pytest

from client.bazaar import ModelBazaar
from client.utils import auth_header, http_get_with_error


@pytest.fixture
def malformed_file():
    new_filename = "malformed.csv"
    shutil.copyfile(__file__, new_filename)
    yield new_filename
    os.remove(new_filename)


@pytest.mark.unit
def test_train_error_handling(malformed_file):
    base_url = "http://127.0.0.1:80/api/"

    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    model_name = f"basic_ndb_{uuid.uuid4()}"
    model = admin_client.train(
        model_name,
        model_options={},
        unsupervised_docs=[__file__],
        supervised_docs=[(malformed_file, "0")],
        is_async=True,
    )

    with pytest.raises(ValueError, match=f"Training Failed for admin/{model_name}"):
        admin_client.await_train(model)

    status_info = admin_client.train_status(model)
    logs = http_get_with_error(
        urljoin(admin_client._base_url, "train/logs"),
        params={"model_identifier": model.model_identifier},
        headers=auth_header(admin_client._access_token),
    ).json()["data"][0]["stderr"]

    warning = "test_train_error_handling.py. Unsupported filetype"
    assert warning in status_info["warnings"][0]
    assert warning in logs

    error = "Error tokenizing data. C error:"
    assert error in status_info["errors"][0]
    assert error in logs
