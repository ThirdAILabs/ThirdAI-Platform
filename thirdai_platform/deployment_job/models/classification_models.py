from abc import abstractmethod
from pathlib import Path
from typing import List, Optional

from deployment_job.models.model import Model
from deployment_job.pydantic_models.inputs import SearchResultsTextClassification
from fastapi import HTTPException, status
from platform_common.logging import JobLogger
from platform_common.logging.logcodes import LogCode
from platform_common.pii.data_types import UnstructuredText, XMLLog
from platform_common.pydantic_models.deployment import DeploymentConfig
from platform_common.thirdai_storage.data_types import (
    DataSample,
    LabelCollection,
    LabelEntity,
    LabelStatus,
    Metadata,
    MetadataStatus,
    SampleStatus,
    TagMetadata,
    TextClassificationData,
    TokenClassificationData,
)
from platform_common.thirdai_storage.storage import DataStorage, SQLiteConnector
from thirdai import bolt


class ClassificationModel(Model):
    def __init__(self, config: DeploymentConfig, logger: JobLogger):
        super().__init__(config=config, logger=logger)
        self.model: bolt.UniversalDeepTransformer = self.load()

    def get_udt_path(self, model_id: Optional[str] = None) -> str:
        model_id = model_id or self.config.model_id
        udt_path = str(self.get_model_dir(model_id) / "model.udt")
        return udt_path

    def load(self):
        return bolt.UniversalDeepTransformer.load(
            self.get_udt_path(self.config.model_id)
        )

    def save(self, model_id):
        self.model.save(self.get_udt_path(model_id))

    @abstractmethod
    def predict(self, **kwargs):
        pass


class TextClassificationModel(ClassificationModel):
    def __init__(self, config: DeploymentConfig, logger: JobLogger):
        super().__init__(config=config, logger=logger)
        self.num_classes = self.model.predict({"text": "test"}).shape[-1]
        self.logger.info(
            f"TextClassificationModel initialized with {self.num_classes} classes",
            code=LogCode.MODEL_INIT,
        )
        self.load_storage()

    def load_storage(self):
        data_storage_path = (
            Path(self.config.model_bazaar_dir)
            / "data"
            / self.config.model_id
            / "data_storage.db"
        )

        try:
            if not data_storage_path.exists():
                self.logger.info(
                    "Data storage path does not exist, creating it",
                    code=LogCode.DATA_STORAGE,
                )

                data_storage_path.parent.mkdir(parents=True, exist_ok=True)

                # For text classification, get the class names from the model
                labels = [self.model.class_name(i) for i in range(self.num_classes)]
                tag_metadata = TagMetadata()
                for label in labels:
                    tag_metadata.add_tag(
                        LabelEntity(name=label, status=LabelStatus.trained)
                    )

                # Connector will instantiate an sqlite db at the specified path if it doesn't exist
                self.data_storage = DataStorage(
                    connector=SQLiteConnector(db_path=data_storage_path)
                )

                self.data_storage.insert_metadata(
                    Metadata(
                        name="tags_and_status",
                        data=tag_metadata,
                        status=MetadataStatus.unchanged,
                    )
                )
            else:
                self.data_storage = DataStorage(
                    connector=SQLiteConnector(db_path=data_storage_path)
                )
            self.logger.info(
                f"Loaded data storage from {data_storage_path}",
                code=LogCode.DATA_STORAGE,
            )
        except Exception as e:
            self.logger.error(
                f"Error loading data storage: {e} for the model {self.config.model_id}",
                code=LogCode.DATA_STORAGE,
            )
            raise e

    def predict(self, text: str, top_k: int, **kwargs):
        try:
            top_k = min(top_k, self.num_classes)
            prediction = self.model.predict({"text": text}, top_k=top_k)
            predicted_classes = [
                (self.model.class_name(class_id), activation)
                for class_id, activation in zip(*prediction)
            ]

            return SearchResultsTextClassification(
                query_text=text,
                predicted_classes=predicted_classes,
            )
        except Exception as e:
            self.logger.error(f"Error predicting: {e}", code=LogCode.MODEL_PREDICT)
            raise e

    def insert_sample(self, sample: TextClassificationData):
        text_sample = DataSample(
            name="text_classification",
            data=sample,
            user_provided=True,
            status=SampleStatus.untrained,
        )
        try:
            self.data_storage.insert_samples(
                samples=[text_sample], override_buffer_limit=True
            )
            self.logger.debug(f"Sample inserted into data storage")
        except Exception as e:
            self.logger.error(f"Error inserting sample: {e}", code=LogCode.DATA_STORAGE)
            raise e

    def get_recent_samples(self, num_samples: int = 5) -> List[TextClassificationData]:
        try:
            recent_samples = self.data_storage.retrieve_samples(
                name="text_classification",
                num_samples=num_samples,
                user_provided=True,  # Assuming we want user-provided samples
            )
            self.logger.debug(
                f"Retrieved {len(recent_samples)} samples from data storage"
            )
            return [sample.data for sample in recent_samples]
        except Exception as e:
            self.logger.error(
                f"Error retrieving samples: {e}", code=LogCode.DATA_STORAGE
            )
            raise e


class TokenClassificationModel(ClassificationModel):
    def __init__(self, config: DeploymentConfig, logger: JobLogger):
        super().__init__(config=config, logger=logger)
        self.load_storage()

    def load_storage(self):
        data_storage_path = (
            Path(self.config.model_bazaar_dir)
            / "data"
            / self.config.model_id
            / "data_storage.db"
        )

        try:
            if not data_storage_path.exists():
                self.logger.info(
                    "Data storage path does not exist, creating it",
                    code=LogCode.DATA_STORAGE,
                )

                data_storage_path.parent.mkdir(parents=True, exist_ok=True)

                tags = self.model.list_ner_tags()
                tag_metadata = TagMetadata()
                for tag in tags:
                    tag_metadata.add_tag(
                        LabelEntity(name=tag, status=LabelStatus.trained)
                    )

                # connector will instantiate an sqlite db at the specified path if it doesn't exist
                self.data_storage = DataStorage(
                    connector=SQLiteConnector(db_path=data_storage_path)
                )

                self.data_storage.insert_metadata(
                    Metadata(
                        name="tags_and_status",
                        data=tag_metadata,
                        status=MetadataStatus.unchanged,
                    )
                )
                self.logger.info(
                    f"Loading data storage from {data_storage_path}",
                    code=LogCode.DATA_STORAGE,
                )

            else:
                self.data_storage = DataStorage(
                    connector=SQLiteConnector(db_path=data_storage_path)
                )
        except Exception as e:
            self.logger.error(
                f"Error loading data storage: {e} for the model {self.config.model_id}",
                code=LogCode.DATA_STORAGE,
            )
            raise e

    def predict(self, text: str, data_type: str, **kwargs):
        try:
            if data_type == "unstructured":
                log = UnstructuredText(text)
            elif data_type == "xml":
                log = XMLLog(text)
            else:
                raise ValueError(
                    "Expected data type to be either 'unstructured' or 'xml'. Found: {data_type}"
                )

            model_predictions = self.model.predict(
                log.inference_sample, top_k=1, as_unicode=True
            )
            result = log.process_prediction(model_predictions)

        except ValueError as e:
            message = f"Error processing prediction: {e}"
            self.logger.error(message, code=LogCode.MODEL_PREDICT)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message,
            )
        except Exception as e:
            message = f"Error processing prediction: {e}"
            self.logger.error(message, code=LogCode.MODEL_PREDICT)
            raise e

        return result

    @property
    def tag_metadata(self) -> TagMetadata:
        # load tags and their status from the storage
        return self.data_storage.get_metadata("tags_and_status").data

    def update_tag_metadata(self, tag_metadata, status: MetadataStatus):
        self.data_storage.insert_metadata(
            metadata=Metadata(name="tags_and_status", data=tag_metadata, status=status)
        )

    def get_labels(self) -> List[str]:
        # load tags and their status from the storage
        return list(self.tag_metadata.tag_status.keys())

    def add_labels(self, labels: LabelCollection):
        try:
            tag_metadata = self.tag_metadata
            for label in labels.tags:
                tag_metadata.add_tag(label)
            # update the metadata entry in the DB
            self.update_tag_metadata(tag_metadata, MetadataStatus.updated)
            self.logger.info(f"Tag metadata updated", code=LogCode.DATA_STORAGE)
        except Exception as e:
            self.logger.error(
                f"Error updating tag metadata: {e}", code=LogCode.DATA_STORAGE
            )
            raise e

    def insert_sample(self, sample: TokenClassificationData):
        try:
            token_tag_sample = DataSample(
                name="ner",
                data=sample,
                user_provided=True,
                status=SampleStatus.untrained,
            )
            self.data_storage.insert_samples(
                samples=[token_tag_sample], override_reservoir_limit=True
            )
            self.logger.debug(f"Sample inserted into data storage")
        except Exception as e:
            self.logger.error(f"Error inserting sample: {e}", code=LogCode.DATA_STORAGE)
            raise e

    def get_recent_samples(self, num_samples: int = 5) -> List[TokenClassificationData]:
        """
        Retrieves the most recent samples from the data storage.

        Args:
            num_samples (int): Number of recent samples to retrieve. Defaults to 5.

        Returns:
            List[TokenClassificationData]: A list of the most recent TokenClassificationData samples.
        """
        try:
            # Retrieve recent samples using the existing data_storage methods
            recent_samples = self.data_storage.retrieve_samples(
                name="ner",
                num_samples=num_samples,
                user_provided=True,  # Assuming we want user-provided samples
            )
            self.logger.debug(
                f"Retrieved {len(recent_samples)} samples from data storage"
            )
            # Return the TokenClassificationData objects directly
            return [sample.data for sample in recent_samples]
        except Exception as e:
            self.logger.error(
                f"Error retrieving samples: {e}", code=LogCode.DATA_STORAGE
            )
            raise e
