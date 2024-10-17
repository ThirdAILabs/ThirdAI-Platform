import os

import pytest

from headless.dag_executor import DAGExecutor
from headless.functions import functions_registry, initialize_flow
from headless.utils import download_from_s3_if_not_exists, normalize_s3_uri


@pytest.fixture(scope="session")
def additional_variables():
    is_merge_group = os.getenv("GITHUB_EVENT_NAME") == "merge_group"
    return {
        "sharded": False,
        "run_name": "ci_run",
        "on_prem": False,
        "generation": is_merge_group,
    }


@pytest.fixture(scope="session")
def local_test_dir():
    local_test_dir = os.getenv("SHARE_DIR")
    if not local_test_dir:
        pytest.fail("Error: SHARE_DIR environment variable is not set.")
    return local_test_dir


@pytest.fixture(scope="session")
def setup_test_data(local_test_dir):
    s3_uris = [
        "s3://thirdai-corp-public/ThirdAI-Enterprise-Test-Data/scifact",
        "s3://thirdai-corp-public/ThirdAI-Enterprise-Test-Data/clinc",
        "s3://thirdai-corp-public/ThirdAI-Enterprise-Test-Data/token",
    ]

    for s3_uri in s3_uris:
        normalized_uri = normalize_s3_uri(s3_uri)
        folder_name = normalized_uri.split("/")[-1]

        download_from_s3_if_not_exists(
            s3_uri, os.path.join(local_test_dir, folder_name)
        )


@pytest.fixture(scope="session")
def dag_executor(additional_variables, setup_test_data):
    dag_executor = DAGExecutor(
        function_registry=functions_registry, global_vars=additional_variables
    )
    return dag_executor


@pytest.fixture(scope="session", autouse=True)
def initialize_environment():
    initialize_flow("http://127.0.0.1:80/api/", "admin@mail.com", "password")


dag_files = [
    ("headless/dag_config.yaml", "Recovery_Backup"),
    ("headless/dag_config.yaml", "GlobalAdmin"),
    ("headless/dag_config.yaml", "TeamAdmin"),
    ("headless/dag_config.yaml", "NDB"),
    ("headless/dag_config.yaml", "UDT"),
    ("headless/dag_config.yaml", "UDT_DATAGEN"),
]


@pytest.mark.parametrize("dag_file, dag_name", dag_files)
def test_dag(dag_executor, dag_file, dag_name):
    event_name = os.getenv("GITHUB_EVENT_NAME")

    # Skip UDT_DATAGEN if not a merge_group
    if dag_name == "UDT_DATAGEN" and event_name != "merge_group":
        pytest.skip(
            f"Skipping UDT_DATAGEN since the event is not merge_group, it's {event_name}"
        )
    dag_executor.load_dags_from_file(dag_file)
    assert dag_executor.execute_dag(dag_name)
