import nltk

nltk.download("punkt_tab")
print("Downloading punkttab")

import argparse
import os

import thirdai
from models.classification_models import (
    TextClassificationModel,
    TokenClassificationModel,
)
from models.finetunable_retriever import FinetunableRetriever
from models.single_mach import SingleMach
from config import TrainConfig, ModelType, NDBVersion, RetrieverType, UDTSubType
from reporter import HttpReporter, Reporter


def get_model(options: TrainConfig, reporter: Reporter):
    model_type = options.model_options.model_type

    if model_type == ModelType.NDB:
        if options.model_options.version_options.version == NDBVersion.v1:
            retriever = options.model_options.version_options.retriever

            if retriever == RetrieverType.finetunable_retriever:
                return FinetunableRetriever(options, reporter)
            elif retriever == RetrieverType.hybrid or retriever == RetrieverType.mach:
                return SingleMach(options, reporter)
            else:
                raise ValueError(f"Unsupported NDB retriever '{retriever.value}'")

        else:
            raise ValueError("NeuralDB v2 is not yet supported")
    elif model_type == ModelType.UDT:
        udt_type = options.model_options.udt_options.udt_sub_type

        if udt_type == UDTSubType.text:
            return TextClassificationModel(options, reporter)
        elif udt_type == UDTSubType.token:
            return TokenClassificationModel(options, reporter)
        else:
            raise ValueError(f"Unsupported UDT subtype '{udt_type.value}'")

    raise ValueError(f"Unsupported model type {model_type.value}")


def load_options():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)

    args = parser.parse_args()

    with open(args.config) as file:
        return TrainConfig.model_validate_json(file.read())


def main():
    options = load_options()

    reporter = HttpReporter(options.model_bazaar_endpoint)

    if options.license_key == "file_license":
        thirdai.licensing.set_path(
            os.path.join(options.model_bazaar_dir, "license/license.serialized")
        )
    else:
        thirdai.licensing.activate(options.license_key)

    model = get_model(options, reporter)

    model.train()


if __name__ == "__main__":
    main()
