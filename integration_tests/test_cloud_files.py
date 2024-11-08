import uuid

import pytest
import requests

from client.bazaar import ModelBazaar


def s3_public_doc():
    return {
        "path": "s3://thirdai-corp-public/ThirdAI-Enterprise-Test-Data/scifact/",
        "location": "s3",
        "options": {},
        "metadata": None,
    }


# Credentials will be passed from env variables
def s3_private_doc():
    return {
        "path": "s3://thirdai-datasets/insert.pdf",
        "location": "s3",
        "options": {},
        "metadata": None,
    }


def azure_public_doc():
    return {
        "path": "https://csg100320028d93f3bc.blob.core.windows.net/test/insert.pdf",
        "location": "azure",
        "options": {},
        "metadata": None,
    }


# Credentials will be passed from env variables
def azure_private_doc():
    return {
        "path": "https://csg100320028d93f3bc.blob.core.windows.net/private-platform/test_folder/",
        "location": "azure",
        "options": {},
        "metadata": None,
    }


def gcp_public_doc():
    return {
        "path": "gs://public-training-platform/sample_nda.pdf",
        "location": "gcp",
        "options": {},
        "metadata": None,
    }


# Credentials will be passed from env variables
def gcp_private_doc():
    return {
        "path": "gs://private-thirdai-platform/test_folder/",
        "location": "gcp",
        "options": {},
        "metadata": None,
    }


# Credentials will be passed from here.
def azure_multiple_docs():
    return [
        {
            "path": "https://csg100320028f116ef3.blob.core.windows.net/container-2/sample_nda.pdf",
            "location": "azure",
            "options": {},
            "metadata": None,
            "cloud_credentials": {
                "azure": {
                    "account_name": "csg100320028f116ef3",
                    "account_key": "MT2x65R1czcqwnz497oAfTWh2y0ucBZ4n9r0j18iDlc77CXO46vnlRc+FVud17eWQvjYSTW/TtyM+AStgmcMSw==",
                }
            },
        },
        {
            "path": "https://csg100320028d9659c0.blob.core.windows.net/container-1/insert.pdf",
            "location": "azure",
            "options": {},
            "metadata": None,
            "cloud_credentials": {
                "azure": {
                    "account_name": "csg100320028d9659c0",
                    "account_key": "2th9sOTrsd1/M8Imw7kr+rHNDLMdUrJB5UVY8/cBOEJOFt5X1z40uj4GrNANuD36m79Xq3QBtp63+AStyOJ/oA==",
                }
            },
        },
    ]


@pytest.mark.parametrize(
    "model_name_prefix, unsupervised_docs, provider, expected_query",
    [
        ("s3_public_ndb", [s3_public_doc()], "s3", "sample query"),
        ("s3_private_ndb", [s3_private_doc()], "s3", "Alice in wonderland"),
        ("azure_public_ndb", [azure_public_doc()], "azure", "Alice in wonderland"),
        ("azure_private_ndb", [azure_private_doc()], "azure", "Alice in wonderland"),
        ("gcp_public_ndb", [gcp_public_doc()], "gcp", "confidentiality agreement"),
        ("gcp_private_ndb", [gcp_private_doc()], "gcp", "confidentiality agreement"),
        (
            "azure_multiple_cred_ndb",
            azure_multiple_docs(),
            "azure",
            "confidentiality agreement",
        ),
    ],
)
@pytest.mark.unit
def test_cloud_training(model_name_prefix, unsupervised_docs, provider, expected_query):
    base_url = "http://127.0.0.1:80/api/"
    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    # Dynamically generate the model name based on the prefix and uuid
    model_name = f"{model_name_prefix}_{uuid.uuid4()}"

    # Train the model with the corresponding file URL and provider
    model = admin_client.train(
        model_name,
        unsupervised_docs=unsupervised_docs,
        model_options={"ndb_options": {"ndb_sub_type": "v2"}},
        supervised_docs=[],  # Empty for this test case
    )
    admin_client.await_train(model)

    # Deploy model and validate results
    ndb_client = admin_client.deploy(model.model_identifier)
    admin_client.await_deploy(ndb_client)

    # Search and validate
    res = ndb_client.search(expected_query, top_k=1)
    assert res["references"][0]["id"] is not None

    # Get signed URL and check access
    signed_url = ndb_client.get_signed_url(
        source=res["references"][0]["source"], provider=provider
    )
    assert signed_url is not None

    # Validate the signed URL using a request
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    response = requests.get(signed_url, headers=headers)
    assert (
        response.status_code == 200
    ), f"Failed to access {provider} signed URL: {signed_url}"

    # Undeploy the model after validation
    admin_client.undeploy(ndb_client)

    # Delete the model
    admin_client.delete(model.model_identifier)
