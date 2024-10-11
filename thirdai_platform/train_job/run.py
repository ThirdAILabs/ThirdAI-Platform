import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import nltk

nltk.download("punkt_tab")
print("Downloading punkttab")

import argparse

import thirdai
from models.classification_models import (
    TextClassificationModel,
    TokenClassificationModel,
)
from models.finetunable_retriever import FinetunableRetriever
from models.neural_db_v2 import NeuralDBV2
from models.single_mach import SingleMach
from platform_common.pydantic_models.training import (
    ModelType,
    NDBSubType,
    RetrieverType,
    TrainConfig,
    UDTSubType,
)
from reporter import HttpReporter, Reporter


def get_model(config: TrainConfig, reporter: Reporter):
    model_type = config.model_options.model_type

    if model_type == ModelType.NDB:
        if config.model_options.ndb_options.ndb_sub_type == NDBSubType.v1:
            retriever = config.model_options.ndb_options.retriever

            if retriever == RetrieverType.finetunable_retriever:
                return FinetunableRetriever(config, reporter)
            elif retriever == RetrieverType.hybrid or retriever == RetrieverType.mach:
                return SingleMach(config, reporter)
            else:
                raise ValueError(f"Unsupported NDB retriever '{retriever.value}'")

        elif config.model_options.ndb_options.ndb_sub_type == NDBSubType.v2:
            return NeuralDBV2(config, reporter)
        else:
            raise ValueError(
                f"Invalid NDB sub type {config.model_options.ndb_options.ndb_sub_type}"
            )
    elif model_type == ModelType.UDT:
        udt_type = config.model_options.udt_options.udt_sub_type

        if udt_type == UDTSubType.text:
            return TextClassificationModel(config, reporter)
        elif udt_type == UDTSubType.token:
            return TokenClassificationModel(config, reporter)
        else:
            raise ValueError(f"Unsupported UDT subtype '{udt_type.value}'")

    raise ValueError(f"Unsupported model type {model_type.value}")


def load_config():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)

    args = parser.parse_args()

    with open(args.config) as file:
        return TrainConfig.model_validate_json(file.read())


def main():
    config = load_config()

    reporter = HttpReporter(config.model_bazaar_endpoint)

    try:
        if config.license_key == "file_license":
            thirdai.licensing.set_path(
                os.path.join(config.model_bazaar_dir, "license/license.serialized")
            )
        else:
            thirdai.licensing.activate(config.license_key)

        model = get_model(config, reporter)

        model.train()
    except Exception as error:
        reporter.report_status(
            config.model_id,
            status="failed",
            message=f"Training failed with error {error}",
        )
        raise error


if __name__ == "__main__":
    main()
