"""
Main module to initialize and retrieve the appropriate model instance.
"""

import os
from pathlib import Path

import thirdai
from file_handler import S3FileHandler
from models.classification_models import (
    TextClassificationModel,
    TokenClassificationModel,
)
from models.ndb_models import ShardedNDB, SingleNDB
from variables import (
    GeneralVariables,
    NDBSubtype,
    NDBTokenVariables,
    TypeEnum,
    UDTSubtype,
)

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
            print('hahahah')
            if general_variables.type == TypeEnum.NDB:
                if general_variables.sub_type == NDBSubtype.sharded:
                    cls._model_instance = ShardedNDB()
                else:
                    cls._model_instance = SingleNDB()
            elif general_variables.type == TypeEnum.UDT:
                if general_variables.sub_type == UDTSubtype.text:
                    cls._model_instance = TextClassificationModel()
                else:
                    cls._model_instance = TokenClassificationModel()
            else:
                raise ValueError("Invalid model type")
        
        print(cls._model_instance, type(cls._model_instance))
        return cls._model_instance


class TokenModelManager:
    _token_model_instance = None

    @classmethod
    def get_instance(cls):
        if cls._token_model_instance is None:
            ndb_token_variables = NDBTokenVariables.load_from_env()
            if not ndb_token_variables.llm_guardrail:
                raise ValueError("Cannot use LLM GuardRails.")
            elif ndb_token_variables.token_model_id:
                cls._token_model_instance = TokenClassificationModel(
                    model_id=ndb_token_variables.token_model_id
                )
            else:
                s3_handler = S3FileHandler()
                current_file_path = Path(__file__).resolve()
                parent_directory = current_file_path.parent.parent
                model_file_path = parent_directory / "ner_pretrained.bolt"
                if not model_file_path.exists():
                    s3_handler.download_file(
                        s3_url="s3://thirdai-corp-public/ner_pretrained.bolt",
                        file_path=str(model_file_path),
                    )
                cls._token_model_instance = TokenClassificationModel(
                    model_path=str(model_file_path)
                )
        return cls._token_model_instance

    @classmethod
    def update_instance(cls, token_model_id):
        cls._token_model_instance = TokenClassificationModel(model_id=token_model_id)


def get_model():
    return ModelManager.get_instance()


def get_token_model():
    return TokenModelManager.get_instance()
