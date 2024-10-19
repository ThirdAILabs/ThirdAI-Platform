from __future__ import annotations

from enum import Enum
from typing import ClassVar, Dict, List, Union
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

"""
These datatypes are helper objects for storing data into a persistent storage 
without the hassle of saving and loading the entire object on disk.

Example Usescase:

NER :
    TokenClassificationSample : Used for storing user provided training data or data generated using our datagen service.
    TagMetaData : Used for storing what tags are present in the pipeline along with their status (trained/untrained)
"""


class LabelStatus(str, Enum):
    trained = "trained"  # if the model has already been trained on the label
    uninserted = "uninserted"  # if label is scheduled to be added to the model

    untrained = "untrained"  # if the label is present in the model but not trained


class LabelEntity(BaseModel):
    name: str
    examples: List[str] = Field(default_factory=list)
    description: str = Field(default="NA")
    status: LabelStatus = LabelStatus.uninserted

    class Config:
        validate_assignment = True

    @field_validator("name", mode="after")
    def uppercase_name(cls, v):
        return v.upper()


class SampleStatus(str, Enum):
    untrained = "untrained"  # if the sample has not been used for training
    trained = "trained"  # if the sample has been used for training


class MetadataStatus(str, Enum):
    updated = "updated"  # if the metadata has been updated
    unchanged = "unchanged"  # if the metadata has not been updated


class LabelCollection(BaseModel):
    tags: List[LabelEntity]


class SerializableBaseModel(BaseModel):
    def serialize(self) -> str:
        return self.model_dump_json()

    @classmethod
    def deserialize(cls, repr: str) -> "SerializableBaseModel":
        return cls.model_validate_json(repr)


# Text Classification Data
class TextClassificationData(SerializableBaseModel):
    datatype: ClassVar[str] = "text_classification"
    text: str
    label: str


# Token Classification Data
class TokenClassificationData(SerializableBaseModel):
    datatype: ClassVar[str] = "token_classification"
    tokens: List[str]
    tags: List[str]


class DataSample(BaseModel):
    """
    A wrapper class that encapsulates different types of data samples (e.g., TextClassificationData,
    TokenClassificationData) for simplified storage and retrieval. It abstracts the serialization
    and deserialization processes, allowing you to handle various data types uniformly.

    **Easy Extension**: To support a new data type, simply define a new data class; DataSample
    will handle serialization without additional changes.
    """

    name: str
    data: Union[TextClassificationData, TokenClassificationData]
    status: SampleStatus = SampleStatus.untrained
    unique_id: str = Field(default_factory=lambda: str(uuid4()))
    user_provided: bool = False

    def serialize_data(self) -> str:
        return self.data.serialize()

    @staticmethod
    def from_serialized(
        type: str,
        unique_id: str,
        name: str,
        serialized_data: str,
        user_provided: bool,
        status: SampleStatus,
    ) -> "DataSample":
        # Deserialize the data based on its type
        if type == TextClassificationData.datatype:
            data = TextClassificationData.deserialize(serialized_data)
        elif type == TokenClassificationData.datatype:
            data = TokenClassificationData.deserialize(serialized_data)
        else:
            raise ValueError(f"Unknown data type: {type}")

        return DataSample(
            name=name,
            data=data,
            unique_id=unique_id,
            user_provided=user_provided,
            status=status,
        )

    @property
    def datatype(self):
        return self.data.datatype


class TagMetadata(SerializableBaseModel):
    datatype: ClassVar[str] = "token_classification_tags"
    tag_status: Dict[str, LabelEntity] = Field(default_factory=dict)

    def set_tag_status(self, tag: str, status: str):
        if tag in self.tag_status:
            self.tag_status[tag].status = status
        else:
            raise ValueError(f"Tag {tag} not found")

    def add_tag(self, tag: LabelEntity):
        if tag.name in self.tag_status:
            raise Exception(f"Tag {tag.name} is already present in the Tag List")

        self.tag_status[tag.name] = tag

    def rollback(self):
        keys_to_remove = [
            tag
            for tag in self.tag_status
            if self.tag_status[tag].status == LabelStatus.uninserted
        ]
        for key in keys_to_remove:
            self.tag_status.pop(key)


class Metadata(BaseModel):
    name: str
    data: TagMetadata
    status: MetadataStatus = MetadataStatus.unchanged

    def serialize_data(self) -> str:
        return self.data.serialize()

    @staticmethod
    def from_serialized(
        type: str, name: str, status: MetadataStatus, serialized_data: str
    ):
        if type == TagMetadata.datatype:
            data = TagMetadata.deserialize(serialized_data)
        else:
            raise ValueError(f"Unknown data type: {type}")

        return Metadata(name=name, data=data, status=status)

    @property
    def datatype(self):
        return self.data.datatype

    def rollback(self):
        self.data.rollback()
        self.status = MetadataStatus.unchanged
