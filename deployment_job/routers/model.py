"""
Main module to initialize and retrieve the appropriate model instance.
"""

import os

import thirdai
from models.classification_models import (
    TextClassificationModel,
    TokenClassificationModel,
)
from models.ndb_models import ShardedNDB, SingleNDB
from variables import GeneralVariables, NDBSubtype, TypeEnum, UDTSubtype

# Initialize thirdai license
general_variables: GeneralVariables = GeneralVariables.load_from_env()

if general_variables.license_key == "file_license":
    thirdai.licensing.set_path(
        os.path.join(general_variables.model_bazaar_dir, "license/license.serialized")
    )
else:
    thirdai.licensing.activate(general_variables.license_key)


# Singleton Practice for Model instances.
class ModelManager:
    _model_instance = None

    @classmethod
    def get_instance(cls):
        """
        Retrieves the appropriate model instance based on general variables.

        Returns:
            The initialized model instance.

        Raises:
            ValueError: If the model type is invalid.
        """
        if cls._model_instance is None:
            if general_variables.type == TypeEnum.NDB:
                if general_variables.sub_type == NDBSubtype.v1:
                    cls._model_instance = SingleNDB()
                else:
                    raise ValueError("Invalid model type")
            elif general_variables.type == TypeEnum.UDT:
                if general_variables.sub_type == UDTSubtype.text:
                    cls._model_instance = TextClassificationModel()
                else:
                    cls._model_instance = TokenClassificationModel()
            else:
                raise ValueError("Invalid model type")

        print(cls._model_instance, type(cls._model_instance))
        return cls._model_instance


def get_model():
    return ModelManager.get_instance()
