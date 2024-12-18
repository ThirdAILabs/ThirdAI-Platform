import datetime
import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from deployment_job.permissions import Permissions
from deployment_job.routers.udt import UDTRouterTokenClassification
from fastapi.testclient import TestClient
from licensing.verify import verify_license
from platform_common.logging import JobLogger
from platform_common.pydantic_models.deployment import (
    DeploymentConfig,
    UDTDeploymentOptions,
    UDTSubType,
)
from thirdai import bolt

DEPLOYMENT_ID = "123"
USER_ID = "abc"
MODEL_ID = "xyz"

THIRDAI_LICENSE = os.path.join(
    os.path.dirname(__file__), "../../tests/ndb_enterprise_license.json"
)

UNSTRUCTURED_QUERY = "My email is shubh@thirdai.com"
XML_QUERY = """
<Employee>
  <Email>
    shubh@thirdai.com
  </Email>
</Employee>
"""

logger = JobLogger(
    log_dir=Path("./tmp"),
    log_prefix="deployment",
    service_type="deployment",
    model_id="model-123",
    model_type="ndb",
    user_id="user-123",
)


@pytest.fixture(scope="function")
def tmp_dir():
    path = "./tmp"
    os.environ["SHARE_DIR"] = path
    os.makedirs(path, exist_ok=True)
    yield path
    shutil.rmtree(path)


def create_token_classification_model(tmp_dir: str):
    verify_license.verify_and_activate(THIRDAI_LICENSE)

    model = bolt.UniversalDeepTransformer(
        data_types={
            "source": bolt.types.text(),
            "target": bolt.types.token_tags(tags=[], default_tag="O"),
        },
        target="target",
        embedding_dimension=10,
    )
    model.add_ner_rule("EMAIL")

    model_dir = os.path.join(tmp_dir, "models", MODEL_ID)
    os.makedirs(model_dir, exist_ok=True)

    model_save_path = os.path.join(model_dir, "model.udt")
    model.save(model_save_path)

    return model_save_path


def mock_verify_permission(permission_type: str = "read"):
    return lambda: ""


def mock_check_permission(token: str, permission_type: str = "read"):
    return True


def mock_deployment_permissions(token):
    return {
        "read": True,
        "write": True,
        "override": True,
        "username": "test",
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=5),
    }


def create_config(tmp_dir: str):
    create_token_classification_model(tmp_dir)

    license_info = verify_license.verify_license(THIRDAI_LICENSE)

    return DeploymentConfig(
        deployment_id=DEPLOYMENT_ID,
        user_id=USER_ID,
        model_id=MODEL_ID,
        model_bazaar_endpoint="",
        model_bazaar_dir=tmp_dir,
        host_dir=os.path.join(tmp_dir, "host_dir"),
        license_key=license_info["boltLicenseKey"],
        model_options=UDTDeploymentOptions(udt_sub_type=UDTSubType.token),
    )


def get_query_result(client: TestClient, query: str, data_type: str):
    res = client.post("/predict", json={"text": query, "data_type": data_type})
    assert res.status_code == 200
    return res.json()["data"]


@pytest.mark.unit
@patch.object(Permissions, "verify_permission", mock_verify_permission)
@patch.object(Permissions, "check_permission", mock_check_permission)
@patch.object(Permissions, "_deployment_permissions", mock_deployment_permissions)
def test_deployment_token_classification_unstructured(tmp_dir):
    config = create_config(tmp_dir)

    router = UDTRouterTokenClassification(config, None, logger)
    client = TestClient(router.router)

    results = get_query_result(client, UNSTRUCTURED_QUERY, "unstructured")[
        "prediction_results"
    ]

    assert results["data_type"] == "unstructured"
    assert results["query_text"] == UNSTRUCTURED_QUERY
    assert results["tokens"] == ["My", "email", "is", "shubh@thirdai.com"]
    assert results["predicted_tags"] == [["O"], ["O"], ["O"], ["EMAIL"]]


@pytest.mark.unit
@patch.object(Permissions, "verify_permission", mock_verify_permission)
@patch.object(Permissions, "check_permission", mock_check_permission)
@patch.object(Permissions, "_deployment_permissions", mock_deployment_permissions)
def test_deployment_token_classification_xml(tmp_dir):
    config = create_config(tmp_dir)

    router = UDTRouterTokenClassification(config, None, logger)
    client = TestClient(router.router)

    results = get_query_result(client, XML_QUERY, "xml")["prediction_results"]

    assert results["data_type"] == "xml"
    assert results["query_text"].strip() == XML_QUERY.strip()
    assert results["predictions"] == [
        {
            "label": "EMAIL",
            "location": {
                "global_char_span": {"start": 25, "end": 42},
                "local_char_span": {"start": 5, "end": 22},
                "xpath_location": {"xpath": "/Employee/Email[1]", "attribute": None},
                "value": "shubh@thirdai.com",
            },
        }
    ]
