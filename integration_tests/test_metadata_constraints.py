import os
from uuid import uuid4

import pytest
from utils import doc_dir

from client.bazaar import ModelBazaar

mark = [pytest.mark.unit]


@pytest.mark.parametrize("on_disk", [True, False])
def test_metadata_constraint_search(on_disk: bool):
    base_url = "http://127.0.0.1:80/api/"
    admin_client = ModelBazaar(base_url)
    admin_client.log_in("admin@mail.com", "password")

    model_name = f"basic_ndb_{uuid4()}"

    unsupervised_docs = [os.path.join(doc_dir(), "metadata_docs.csv")]
    doc_options = {
        doc: {
            "csv_strong_columns": ["text"],
            "csv_weak_columns": ["keywords"],
            "csv_metadata_columns": [
                "integer_col",
                "float_col",
                "string_col",
                "bool_col",
            ],
        }
        for doc in unsupervised_docs
    }

    model = admin_client.train(
        model_name,
        unsupervised_docs=unsupervised_docs,
        model_options={"on_disk": on_disk},
        doc_options=doc_options,
    )

    admin_client.await_train(model)

    ndb_client = admin_client.deploy(model.model_identifier)
    admin_client.await_deploy(ndb_client)

    res = ndb_client.search(
        query="Velit magnam labore numquam ipsum.",
        top_k=5,
        constraints={
            "integer_col": {
                "constraint_type": "InRange",
                "min_value": -10,
                "max_value": 10,
            }
        },
    )

    assert all(
        (-10 <= result["metadata"]["integer_col"] <= 10) for result in res["references"]
    )

    res = ndb_client.search(
        query="Velit magnam labore numquam ipsum.",
        top_k=5,
        constraints={
            "float_col": {
                "constraint_type": "InRange",
                "min_value": -80.56,
                "max_value": -75.456,
            }
        },
    )

    assert all(
        (-80.56 <= result["metadata"]["float_col"] <= -75.456)
        for result in res["references"]
    )

    res = ndb_client.search(
        query="Velit magnam labore numquam ipsum.",
        top_k=5,
        constraints={
            "string_col": {
                "constraint_type": "AnyOf",
                "values": ["lemon", "elderberry"],
            },
            "bool_col": {"constraint_type": "EqualTo", "value": True},
        },
    )

    assert all(
        result["metadata"]["string_col"] in ["lemon", "elderberry"]
        and result["metadata"]["bool_col"] == True
        for result in res["references"]
    )
