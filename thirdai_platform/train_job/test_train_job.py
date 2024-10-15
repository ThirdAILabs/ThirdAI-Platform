import os
import shutil
from typing import Dict

import pytest
from config import (
    DatagenOptions,
    FileInfo,
    JobOptions,
    NDBData,
    NDBOptions,
    NDBv1Options,
    NDBv2Options,
    TextClassificationOptions,
    TokenClassificationDatagenOptions,
    TokenClassificationOptions,
    TrainConfig,
    UDTData,
    UDTOptions,
)
from feedback_logs import AssociateLog, FeedbackLog, ImplicitUpvoteLog, UpvoteLog
from reporter import Reporter
from run import get_model
from thirdai import bolt, licensing
from thirdai import neural_db as ndb
from thirdai import neural_db_v2 as ndbv2

pytestmark = [pytest.mark.unit]


class DummyReporter(Reporter):
    def report_complete(self, model_id: str, metadata: Dict[str, str]):
        pass

    def report_status(self, model_id: str, status: str, message: str = ""):
        pass


MODEL_BAZAAR_DIR = "./model_bazaar_tmp"

THIRDAI_LICENSE = "236C00-47457C-4641C5-52E3BB-3D1F34-V3"


def file_dir():
    return os.path.join(os.path.dirname(__file__), "sample_docs")


@pytest.fixture(autouse=True, scope="function")
def create_tmp_model_bazaar_dir():
    os.makedirs(MODEL_BAZAAR_DIR)
    yield
    shutil.rmtree(MODEL_BAZAAR_DIR)


def run_ndb_train_job(ndb_options, extra_supervised_files=[]):
    licensing.activate(THIRDAI_LICENSE)

    source_id = ndb.CSV(
        os.path.join(file_dir(), "articles.csv"),
        weak_columns=["text"],
        metadata={"a": 140},
    ).hash

    config = TrainConfig(
        model_bazaar_dir=MODEL_BAZAAR_DIR,
        license_key=THIRDAI_LICENSE,
        model_bazaar_endpoint="",
        model_id="ndb_123",
        data_id="data_123",
        model_options=NDBOptions(ndb_options=ndb_options),
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
                    doc_id=source_id,
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

    model = get_model(config, DummyReporter())

    model.train()

    return os.path.join(MODEL_BAZAAR_DIR, "models", "ndb_123", "model.ndb")


@pytest.mark.parametrize(
    "ndb_options",
    [NDBv1Options(), NDBv1Options(retriever="mach", mach_options={})],
)
def test_ndbv1_train(ndb_options):
    db_path = run_ndb_train_job(ndb_options)

    db = ndb.NeuralDB.from_checkpoint(db_path)

    assert len(db.sources()) == 3


@pytest.fixture()
def feedback_train_file():
    logs = [
        UpvoteLog(chunk_ids=[10], queries=["some random query to upvote"]),
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


def test_ndbv2_train(feedback_train_file):
    db_path = run_ndb_train_job(
        ndb_options=NDBv2Options(),
        extra_supervised_files=[FileInfo(path=feedback_train_file, location="local")],
    )

    db = ndbv2.NeuralDB.load(db_path)

    assert len(db.documents()) == 3


def test_udt_text_train():
    licensing.activate(THIRDAI_LICENSE)
    config = TrainConfig(
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
                )
            ],
            test_files=[
                FileInfo(
                    path=os.path.join(file_dir(), "articles.csv"), location="local"
                )
            ],
        ),
        job_options=JobOptions(),
    )

    model = get_model(config, DummyReporter())

    model.train()

    bolt.UniversalDeepTransformer.load(
        os.path.join(MODEL_BAZAAR_DIR, "models", "udt_123", "model.udt")
    )


def test_udt_token_train():
    licensing.activate(THIRDAI_LICENSE)
    config = TrainConfig(
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
            supervised_files=[
                FileInfo(path=os.path.join(file_dir(), "ner.csv"), location="local")
            ],
            test_files=[
                FileInfo(path=os.path.join(file_dir(), "ner.csv"), location="local")
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
                    }
                ],
                num_sentences_to_generate=1000,
                num_samples_per_tag=None,
                samples=None,
                templates_per_sample=10,
            ),
        ),
    )

    model = get_model(config, DummyReporter())

    model.train()

    bolt.UniversalDeepTransformer.load(
        os.path.join(MODEL_BAZAAR_DIR, "models", "udt_123", "model.udt")
    )
