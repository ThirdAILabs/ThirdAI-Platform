from abc import abstractmethod
from logging import Logger
from pathlib import Path
from typing import List, Optional

from deployment_job.models.model import Model
from deployment_job.pydantic_models.inputs import (
    SearchResultsTextClassification,
    SearchResultsTokenClassification,
)
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
    TokenClassificationData,
)
from platform_common.thirdai_storage.storage import DataStorage, SQLiteConnector
from thirdai import bolt


class ClassificationModel(Model):
    def __init__(self, config: DeploymentConfig, logger: Logger):
        super().__init__(config=config, logger=logger)
        self.model: bolt.UniversalDeepTransformer = self.load()

    def get_udt_path(self, model_id: Optional[str] = None) -> str:
        model_id = model_id or self.config.model_id
        return str(self.get_model_dir(model_id) / "model.udt")

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
    def __init__(self, config: DeploymentConfig, logger: Logger):
        super().__init__(config=config, logger=logger)
        self.num_classes = self.model.predict({"text": "test"}).shape[-1]

    def predict(self, text: str, top_k: int, **kwargs):
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


class TokenClassificationModel(ClassificationModel):
    def __init__(self, config: DeploymentConfig, logger: Logger):
        super().__init__(config=config, logger=logger)
        self.load_storage()

    def predict(self, text: str, **kwargs):
        predicted_tags = self.model.predict({"source": text}, top_k=1)
        predictions = []
        for predicted_tag in predicted_tags:
            predictions.append([x[0] for x in predicted_tag])

        return SearchResultsTokenClassification(
            query_text=text,
            tokens=text.split(),
            predicted_tags=predictions,
        )

    def load_storage(self):
        data_storage_path = (
            Path(self.config.model_bazaar_dir)
            / "data"
            / self.config.model_id
            / "data_storage.db"
        )

        try:
            if not data_storage_path.exists():
                self.logger.info(f"Data storage path does not exist, creating it")

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

            else:
                self.data_storage = DataStorage(
                    connector=SQLiteConnector(db_path=data_storage_path)
                )
        except Exception as e:
            self.logger.error(
                f"Error loading data storage: {e} for the model {self.config.model_id}"
            )
            raise e

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
        tag_metadata = self.tag_metadata
        for label in labels.tags:
            tag_metadata.add_tag(label)

        # update the metadata entry in the DB
        self.update_tag_metadata(tag_metadata, MetadataStatus.updated)

    def insert_sample(self, sample: TokenClassificationData):
        token_tag_sample = DataSample(
            name="ner", data=sample, user_provided=True, status=SampleStatus.untrained
        )
        self.data_storage.insert_samples(
            samples=[token_tag_sample], override_buffer_limit=True
        )

    def get_recent_samples(self, num_samples: int = 5) -> List[TokenClassificationData]:
        """
        Retrieves the most recent samples from the data storage.

        Args:
            num_samples (int): Number of recent samples to retrieve. Defaults to 5.

        Returns:
            List[TokenClassificationData]: A list of the most recent TokenClassificationData samples.
        """
        # Retrieve recent samples using the existing data_storage methods
        recent_samples = self.data_storage.retrieve_samples(
            name="ner",
            num_samples=num_samples,
            user_provided=True,  # Assuming we want user-provided samples
        )

        # Return the TokenClassificationData objects directly
        return [sample.data for sample in recent_samples]
