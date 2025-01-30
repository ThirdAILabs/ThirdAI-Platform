import os
import shutil
from pathlib import Path
from typing import Dict

import pandas as pd
import pytest
from licensing.verify import verify_license
from platform_common.logging import JobLogger
from platform_common.pydantic_models.feedback_logs import (
    AssociateLog,
    FeedbackLog,
    ImplicitUpvoteLog,
    UpvoteLog,
)
from platform_common.pydantic_models.training import (
    DatagenOptions,
    FileInfo,
    JobOptions,
    NDBData,
    NDBOptions,
    TextClassificationOptions,
    TokenClassificationDatagenOptions,
    TokenClassificationOptions,
    TrainConfig,
    UDTData,
    UDTOptions,
    UDTTrainOptions,
)
from thirdai import bolt
from thirdai import neural_db as ndb
from thirdai import neural_db_v2 as ndbv2
from train_job.models.classification_models import TokenClassificationModel
from train_job.reporter import Reporter
from train_job.run import get_model

pytestmark = [pytest.mark.unit]


class DummyReporter(Reporter):
    def report_complete(self, model_id: str, metadata: Dict[str, str]):
        pass

    def report_status(self, model_id: str, status: str, message: str = ""):
        pass

    def report_warning(self, model_id: str, message: str):
        pass


MODEL_BAZAAR_DIR = "./model_bazaar_tmp"

THIRDAI_LICENSE = os.path.join(
    os.path.dirname(__file__), "../tests/ndb_enterprise_license.json"
)

logger = JobLogger(
    log_dir=Path("./model_bazaar_tmp"),
    log_prefix="train",
    service_type="train",
    model_id="model-123",
    model_type="ndb",
    user_id="user-123",
)


def file_dir():
    return os.path.join(os.path.dirname(__file__), "sample_docs")


@pytest.fixture()
def dummy_ner_file():
    source, target = "Shubh", "O"
    df = pd.DataFrame({"text": [source] * 200_000, "tags": [target] * 200_000})
    file_path = os.path.join(file_dir(), "dummy_ner.csv")

    df.to_csv(file_path, index=False)
    yield file_path
    os.remove(file_path)


@pytest.fixture(autouse=True, scope="function")
def create_tmp_model_bazaar_dir():
    os.makedirs(MODEL_BAZAAR_DIR, exist_ok=True)
    yield
    shutil.rmtree(MODEL_BAZAAR_DIR)


def run_ndb_train_job(extra_supervised_files=[], on_disk=True):
    verify_license.verify_and_activate(THIRDAI_LICENSE)

    source_id = ndb.CSV(
        os.path.join(file_dir(), "articles.csv"),
        weak_columns=["text"],
        metadata={"a": 140},
    ).hash

    config = TrainConfig(
        user_id="user_123",
        model_bazaar_dir=MODEL_BAZAAR_DIR,
        license_key=THIRDAI_LICENSE,
        model_bazaar_endpoint="",
        model_id="ndb_123",
        data_id="data_123",
        model_options=NDBOptions(on_disk=on_disk),
        data=NDBData(
            unsupervised_files=[
                FileInfo(
                    path=os.path.join(file_dir(), "articles.csv"),
                    location="local",
                    options={"csv_id_column": None, "csv_weak_columns": ["text"]},
                    metadata={"a": 140},
                ),
                FileInfo(
                    path=os.path.join(file_dir(), "four_english_words.docx"),
                    location="local",
                    metadata={"file_type": "docx", "a": 200},
                ),
                FileInfo(
                    path=os.path.join(file_dir(), "mutual_nda.pdf"),
                    location="local",
                    metadata={"file_type": "pdf"},
                    options={"title_as_keywords": True, "keyword_weight": 5},
                ),
            ],
            supervised_files=[
                FileInfo(
                    path=os.path.join(file_dir(), "supervised.csv"),
                    location="local",
                    source_id=source_id,
                    options={"csv_query_column": "query", "csv_id_column": "id"},
                ),
                *extra_supervised_files,
            ],
            test_files=[
                FileInfo(
                    path=os.path.join(file_dir(), "supervised.csv"),
                    location="local",
                )
            ],
        ),
        job_options=JobOptions(),
    )

    model = get_model(config, DummyReporter(), logger)

    model.train()

    return os.path.join(MODEL_BAZAAR_DIR, "models", "ndb_123", "model.ndb")


@pytest.fixture()
def feedback_train_file():
    logs = [
        UpvoteLog(
            chunk_ids=[10],
            queries=["some random query to upvote"],
            reference_texts=["Corresponding reference text"],
        ),
        AssociateLog(
            sources=["premier league teams"], targets=["arsenal and manchester united"]
        ),
        ImplicitUpvoteLog(
            chunk_id=11,
            query="what is the answer to my query",
            event_desc="read reference",
        ),
    ]

    filename = "./dummy_rlhf_data.jsonl"

    with open(filename, "w") as file:
        file.writelines(FeedbackLog(event=log).model_dump_json() + "\n" for log in logs)

    yield filename

    os.remove(filename)


@pytest.mark.parametrize("on_disk", [True, False])
def test_ndbv2_train(feedback_train_file, on_disk):
    db_path = run_ndb_train_job(
        extra_supervised_files=[FileInfo(path=feedback_train_file, location="local")],
        on_disk=on_disk,
    )

    db = ndbv2.FastDB.load(db_path)

    assert len(db.documents()) == 3


def test_udt_text_train():
    verify_license.verify_and_activate(THIRDAI_LICENSE)

    os.environ["AZURE_ACCOUNT_NAME"] = "csg100320028d93f3bc"
    config = TrainConfig(
        user_id="user_123",
        model_bazaar_dir=MODEL_BAZAAR_DIR,
        license_key=THIRDAI_LICENSE,
        model_bazaar_endpoint="",
        model_id="udt_123",
        data_id="data_123",
        model_options=UDTOptions(
            udt_options=TextClassificationOptions(
                text_column="text", label_column="id", n_target_classes=100
            ),
        ),
        data=UDTData(
            supervised_files=[
                FileInfo(
                    path=os.path.join(file_dir(), "articles.csv"), location="local"
                ),
                FileInfo(
                    path="https://csg100320028d93f3bc.blob.core.windows.net/test/articles.csv",
                    location="azure",
                ),
            ],
            test_files=[
                FileInfo(
                    path=os.path.join(file_dir(), "articles.csv"), location="local"
                ),
                FileInfo(
                    path="https://csg100320028d93f3bc.blob.core.windows.net/test/articles.csv",
                    location="azure",
                ),
            ],
        ),
        job_options=JobOptions(),
    )

    model = get_model(config, DummyReporter(), logger)

    model.train()

    bolt.UniversalDeepTransformer.load(
        os.path.join(MODEL_BAZAAR_DIR, "models", "udt_123", "model.udt")
    )


@pytest.fixture()
def doc_classification_files():
    base_dir = os.path.join(file_dir(), "doc_classification_test_data")
    file_list = []

    for label in ["positive", "neutral", "negative"]:
        label_dir = os.path.join(base_dir, label)
        for file in os.listdir(label_dir):
            if file.endswith(".pdf"):
                file_list.append(
                    FileInfo(
                        path=os.path.join(label_dir, file),
                        location="local",
                        metadata={"label": label},
                    )
                )
    return file_list


def test_udt_document_classification(doc_classification_files):
    verify_license.verify_and_activate(THIRDAI_LICENSE)

    config = TrainConfig(
        user_id="user_123",
        model_bazaar_dir=MODEL_BAZAAR_DIR,
        license_key=THIRDAI_LICENSE,
        model_bazaar_endpoint="",
        model_id="udt_123",
        data_id="data_123",
        model_options=UDTOptions(
            udt_options=TextClassificationOptions(
                text_column="text",
                label_column="label",
                n_target_classes=3,
                word_limit=1000,
                udt_sub_type="document",
            ),
            train_options=UDTTrainOptions(test_split=0.1),
        ),
        data=UDTData(supervised_files=doc_classification_files),
        job_options=JobOptions(allocation_cores=2, allocation_memory=16000),
    )

    model = get_model(config, DummyReporter(), logger)
    model.train()

    # Verify model output
    model_path = os.path.join(MODEL_BAZAAR_DIR, "models", "udt_123", "model.udt")
    assert os.path.exists(model_path)
    trained_model = bolt.UniversalDeepTransformer.load(model_path)


@pytest.mark.parametrize("test_split", [0, 0.25])
def test_udt_token_train(test_split):
    verify_license.verify_and_activate(THIRDAI_LICENSE)

    os.environ["AZURE_ACCOUNT_NAME"] = "csg100320028d93f3bc"
    config = TrainConfig(
        user_id="user_123",
        model_bazaar_dir=MODEL_BAZAAR_DIR,
        license_key=THIRDAI_LICENSE,
        model_bazaar_endpoint="",
        model_id="udt_123",
        data_id="data_123",
        model_options=UDTOptions(
            udt_options=TokenClassificationOptions(
                target_labels=["NAME", "EMAIL"],
                source_column="text",
                target_column="tags",
                default_tag="O",
            ),
            train_options=UDTTrainOptions(test_split=test_split),
        ),
        data=UDTData(
            supervised_files=[
                FileInfo(path=os.path.join(file_dir(), "ner.csv"), location="local"),
                FileInfo(
                    path="https://csg100320028d93f3bc.blob.core.windows.net/test/ner.csv",
                    location="azure",
                ),
            ],
            test_files=[
                FileInfo(path=os.path.join(file_dir(), "ner.csv"), location="local"),
                FileInfo(
                    path="https://csg100320028d93f3bc.blob.core.windows.net/test/ner.csv",
                    location="azure",
                ),
            ],
        ),
        job_options=JobOptions(),
        datagen_options=DatagenOptions(
            task_prompt="token classification",
            llm_provider="openai",
            datagen_options=TokenClassificationDatagenOptions(
                sub_type="token",
                tags=[
                    {
                        "name": "NAME",
                        "examples": ["shubh"],
                        "description": "name of person",
                        "status": "uninserted",
                    },
                    {
                        "name": "EMAIL",
                        "examples": ["shubh@gmail.com"],
                        "description": "email of person",
                        "status": "uninserted",
                    },
                ],
                num_sentences_to_generate=1000,
                num_samples_per_tag=None,
                samples=None,
                templates_per_sample=10,
            ),
        ),
    )

    model = get_model(config, DummyReporter(), logger)

    model.train()

    boltmodel = bolt.UniversalDeepTransformer.load(
        os.path.join(MODEL_BAZAAR_DIR, "models", "udt_123", "model.udt")
    )

    predictions = boltmodel.predict({"text": "shubh@gmail.com"})

    assert predictions[0][0][0] == "EMAIL", f"predictions : {predictions}"


def test_udt_token_train_with_balancing(dummy_ner_file):
    verify_license.verify_and_activate(THIRDAI_LICENSE)

    config = TrainConfig(
        user_id="user_123",
        model_bazaar_dir=MODEL_BAZAAR_DIR,
        license_key=THIRDAI_LICENSE,
        model_bazaar_endpoint="",
        model_id="udt_123",
        data_id="data_123",
        model_options=UDTOptions(
            udt_options=TokenClassificationOptions(
                target_labels=["NAME", "EMAIL"],
                source_column="text",
                target_column="tags",
                default_tag="O",
            ),
        ),
        data=UDTData(
            supervised_files=[FileInfo(path=dummy_ner_file, location="local")],
        ),
        job_options=JobOptions(),
        datagen_options=DatagenOptions(
            task_prompt="token classification",
            datagen_options=TokenClassificationDatagenOptions(
                sub_type="token",
                tags=[
                    {
                        "name": "NAME",
                    },
                    {
                        "name": "EMAIL",
                    },
                ],
            ),
        ),
    )

    model: TokenClassificationModel = get_model(config, DummyReporter(), logger)
    assert (
        model.find_and_save_balancing_samples() is None
    ), "No Balancing Samples without training"

    model.train()

    storage = model.data_storage
    assert storage.connector.get_sample_count("ner") == 100_000

    model.find_and_save_balancing_samples()
    assert os.path.exists(
        model._balancing_samples_path
    ), "Balancing Samples Path does not exist"

    df = pd.read_csv(model._balancing_samples_path)
    assert len(df) == model._num_balancing_samples

    assert df["text"][0] == "Shubh"
    assert df["tags"][0] == "O"
    assert df["user_provided"][0] == False
