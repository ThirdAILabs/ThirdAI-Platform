"""
Main module to initialize and retrieve the appropriate model instance.
"""

import os
import threading

import thirdai
from models.classification_models import (
    TextClassificationModel,
    TokenClassificationModel,
)
from models.ndb_models import NDBV1Model, NDBV2Model
from variables import GeneralVariables, ModelType, NDBSubType, UDTSubType

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
    _lock = threading.Lock()  # Initialize a lock for thread safety

    @classmethod
    def get_instance(cls):
        """
        Retrieves the appropriate model instance based on the mode requested.

        Args:
            write_mode (bool): Whether to retrieve the write-mode model instance.

        Returns:
            The initialized model instance.

        Raises:
            ValueError: If the model type is invalid.
        """
        with cls._lock:
            if cls._model_instance is None:
                cls._model_instance = cls._initialize_model(
                    write_mode=not general_variables.autoscaling_enabled
                )
            return cls._model_instance

    @classmethod
    def _initialize_model(cls, write_mode: bool):
        """
        Initializes and returns the appropriate model instance based on general variables.
        """
        if general_variables.type == ModelType.NDB:
            if general_variables.sub_type == NDBSubType.v1:
                return NDBV1Model(write_mode=write_mode)
            elif general_variables.sub_type == NDBSubType.v2:
                return NDBV2Model(write_mode=write_mode)
            else:
                raise ValueError(f"Invalid NDB sub type {general_variables.sub_type}.")
        elif general_variables.type == ModelType.UDT:
            if general_variables.sub_type == UDTSubType.text:
                return TextClassificationModel()
            elif general_variables.sub_type == UDTSubType.token:
                return TokenClassificationModel()
            else:
                raise ValueError("Invalid UDT sub type.")
        else:
            raise ValueError("Invalid model type")

    @classmethod
    def reset_instances(cls):
        """
        Resets both read and write model instances to force reloading of the models.
        """
        with cls._lock:
            cls._model_instance = None


def get_model():
    return ModelManager.get_instance()
