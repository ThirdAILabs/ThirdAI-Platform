from abc import abstractmethod
from pathlib import Path
from typing import List, Optional

from config import DeploymentConfig
from models.model import Model
from pydantic_models import inputs
from thirdai import bolt

from thirdai_platform.common.thirdai_storage.data_types import (
    DataSample,
    LabelCollection,
    Metadata,
    MetadataStatus,
    SampleStatus,
    TagMetadata,
    TokenClassificationData,
)
from thirdai_platform.common.thirdai_storage.storage import DataStorage, SQLiteConnector


class ClassificationModel(Model):
    def __init__(self, config: DeploymentConfig):
        super().__init__(config=config)
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
    def __init__(self, config: DeploymentConfig):
        super().__init__(config=config)
        self.num_classes = self.model.predict({"text": "test"}).shape[-1]

    def predict(self, text: str, top_k: int, **kwargs):
        top_k = min(top_k, self.num_classes)
        prediction = self.model.predict({"text": text}, top_k=top_k)
        predicted_classes = [
            (self.model.class_name(class_id), activation)
            for class_id, activation in zip(*prediction)
        ]

        return inputs.SearchResultsTextClassification(
            query_text=text,
            predicted_classes=predicted_classes,
        )


class TokenClassificationModel(ClassificationModel):
    def __init__(self, config: DeploymentConfig):
        super().__init__(config=config)
        self.load_storage()

    def predict(self, text: str, **kwargs):
        predicted_tags = self.model.predict({"source": text}, top_k=1)
        predictions = []
        for predicted_tag in predicted_tags:
            predictions.append([x[0] for x in predicted_tag])

        return inputs.SearchResultsTokenClassification(
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

        # connector will instantiate an sqlite db at the specified path if it doesn't exist
        self.data_storage = DataStorage(
            connector=SQLiteConnector(db_path=data_storage_path)
        )

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

    def get_recent_samples(self, limit: int = 5) -> List[dict]:
        # Retrieve recent samples using the existing data_storage methods
        recent_samples = self.data_storage.retrieve_samples(
            name="ner",
            num_samples=limit,
            user_provided=True,  # Assuming we want user-provided samples
        )

        # Convert DataSample objects to dictionaries
        return [
            {
                "tokens": sample.data.tokens,
                "tags": sample.data.tags,
            }
            for sample in recent_samples
        ]
