raise ValueError("lolllll")
import nltk

nltk.download("punkt_tab")
print("Downloading punkttab")

import os

import thirdai
from models.classification_models import (
    TextClassificationModel,
    TokenClassificationModel,
)
from models.finetunable_retriever import FinetunableRetriever
from models.multiple_mach import MultipleMach
from models.shard_mach import ShardMach
from models.single_mach import SingleMach
from variables import (
    GeneralVariables,
    NDBSubType,
    NeuralDBVariables,
    RetrieverEnum,
    TypeEnum,
    UDTSubType,
)

# Load general variables from environment
general_variables: GeneralVariables = GeneralVariables.load_from_env()


def main():
    """
    Main function to initialize and train the appropriate model based on environment variables.
    """
    if general_variables.type == TypeEnum.NDB:
        ndb_variables: NeuralDBVariables = NeuralDBVariables.load_from_env()
        if general_variables.sub_type == NDBSubType.single:
            if ndb_variables.retriever == RetrieverEnum.FINETUNABLE_RETRIEVER:
                model = FinetunableRetriever()
                model.train()
            else:
                model = SingleMach()
                model.train()
        elif general_variables.sub_type == NDBSubType.shard_allocation:
            if ndb_variables.retriever == RetrieverEnum.FINETUNABLE_RETRIEVER:
                raise ValueError("Currently Not supported")
            else:
                model = MultipleMach()
                model.train()
        else:
            model = ShardMach()
            model.train()
    elif general_variables.type == TypeEnum.UDT:
        if general_variables.sub_type == UDTSubType.text:
            model = TextClassificationModel()
            model.train()
        elif general_variables.sub_type == UDTSubType.token:
            model = TokenClassificationModel()
            model.train()
        else:
            raise ValueError("Currently Not supported")


if __name__ == "__main__":
    # Set the license for ThirdAI based on the environment variable
    if general_variables.license_key == "file_license":
        thirdai.licensing.set_path(
            os.path.join(
                general_variables.model_bazaar_dir, "license/license.serialized"
            )
        )
    else:
        thirdai.licensing.activate(general_variables.license_key)

    # Run the main function
    main()
