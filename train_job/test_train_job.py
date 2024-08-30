import os
import shutil
from typing import Dict

import pytest
from options import (
    BaseOptions,
    FileInfo,
    NDBOptions,
    NDBv1Options,
    TextClassificationOptions,
    TokenClassificationOptions,
    UDTOptions,
)
from reporter import Reporter
from run import get_model
from thirdai import bolt
from thirdai import neural_db as ndb

pytestmark = [pytest.mark.unit]


class DummyReporter(Reporter):
    def report_complete(self, model_id: str, metadata: Dict[str, str]):
        pass

    def report_status(self, model_id: str, status: str, message: str = ""):
        pass


MODEL_BAZAAR_DIR = "./model_bazaar_tmp"


def file_dir():
    return os.path.join(os.path.dirname(__file__), "sample_docs")


@pytest.fixture(autouse=True, scope="function")
def create_tmp_model_bazaar_dir():
    os.makedirs(MODEL_BAZAAR_DIR)
    yield
    shutil.rmtree(MODEL_BAZAAR_DIR)


@pytest.mark.parametrize(
    "version_options",
    [NDBv1Options(), NDBv1Options(retriever="mach", mach_options={})],
)
def test_ndb_train(version_options):
    options = BaseOptions(
        model_bazaar_dir=MODEL_BAZAAR_DIR,
        license_key="",
        model_bazaar_endpoint="",
        model_id="ndb_123",
        data_id="data_123",
        model_options=NDBOptions(
            version_options=version_options,
            unsupervised_files=[
                FileInfo(
                    path=os.path.join(file_dir(), "articles.csv"),
                    options={"csv_id_column": None, "csv_weak_columns": ["text"]},
                    metadata={"a": 140},
                ),
                FileInfo(
                    path=os.path.join(file_dir(), "four_english_words.docx"),
                    metadata={"file_type": "docx", "a": 200},
                ),
                FileInfo(
                    path=os.path.join(file_dir(), "mutual_nda.pdf"),
                    metadata={"file_type": "pdf"},
                ),
            ],
        ),
    )

    model = get_model(options, DummyReporter())

    model.train()

    db = ndb.NeuralDB.from_checkpoint(
        os.path.join(MODEL_BAZAAR_DIR, "models", "ndb_123", "model.ndb")
    )

    assert len(db.sources()) == 3


def test_udt_text_train():
    options = BaseOptions(
        model_bazaar_dir=MODEL_BAZAAR_DIR,
        license_key="",
        model_bazaar_endpoint="",
        model_id="udt_123",
        data_id="data_123",
        model_options=UDTOptions(
            udt_options=TextClassificationOptions(
                text_column="text", label_column="id", n_target_classes=100
            ),
            train_files=[FileInfo(path=os.path.join(file_dir(), "articles.csv"))],
            test_files=[FileInfo(path=os.path.join(file_dir(), "articles.csv"))],
        ),
    )

    model = get_model(options, DummyReporter())

    model.train()

    bolt.UniversalDeepTransformer.load(
        os.path.join(MODEL_BAZAAR_DIR, "models", "udt_123", "model.udt")
    )


def test_udt_token_train():
    options = BaseOptions(
        model_bazaar_dir=MODEL_BAZAAR_DIR,
        license_key="",
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
            train_files=[FileInfo(path=os.path.join(file_dir(), "ner.csv"))],
            test_files=[FileInfo(path=os.path.join(file_dir(), "ner.csv"))],
        ),
    )

    model = get_model(options, DummyReporter())

    model.train()

    bolt.UniversalDeepTransformer.load(
        os.path.join(MODEL_BAZAAR_DIR, "models", "udt_123", "model.udt")
    )
