from __future__ import annotations

import json
import re
import typing
import uuid
from abc import abstractmethod, abstractproperty, abstractstaticmethod
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import UUID


class DataType:

    @abstractmethod
    def serialize(self) -> str:
        # can encode the data
        pass

    @abstractstaticmethod
    def deserialize(name: str, repr: str):
        # can decode the data
        pass

    @property
    def name(self):
        return self._name


class DataSample(DataType):
    def __init__(self, unique_id=None):
        self._uuid = unique_id if unique_id is not None else str(uuid.uuid4())

    @property
    def uuid(self):
        return self._uuid

    @abstractstaticmethod
    def deserialize(name: str, repr: str, unique_id: str):
        # can decode the data
        pass


class TextClassificationSample(DataSample):
    datatype = "text_classification"

    def __init__(self, name: str, text: str, label: str, unique_id: str = None):
        super().__init__(unique_id=unique_id)

        self._text = text
        self._label = label
        self._name = name

    def serialize(self) -> str:
        return json.dumps({"text": self._text, "label": self._label})

    @staticmethod
    def deserialize(name, repr, unique_id) -> str:
        data = json.loads(repr)
        return TextClassificationSample(
            name=name, text=data["text"], label=data["label"], unique_id=unique_id
        )


class TokenClassificationSample(DataSample):
    datatype = "token_classification"

    def __init__(
        self,
        name: str,
        tokens: typing.List[str],
        tags: typing.List[str],
        unique_id: str = None,
    ):
        super().__init__(unique_id=unique_id)

        self._tokens = tokens
        self._tags = tags
        self._name = name

    def serialize(self) -> str:
        return json.dumps({"tokens": self._tokens, "tags": self._tags})

    @staticmethod
    def deserialize(name, repr, unique_id):
        data = json.loads(repr)
        return TokenClassificationSample(
            tokens=data["tokens"], tags=data["tags"], name=name, unique_id=unique_id
        )


class UserFeedBack(DataType):
    def __init__(self, sample_uuid):
        # There cannot be a feedback without a corresponding sample
        self._sample_uuid = sample_uuid

    @property
    def sample_uuid(self):
        return self._sample_uuid

    @abstractstaticmethod
    def deserialize(sample_uuid: str, name: str, repr: str):
        # can decode the data
        pass


class TokenClassificationFeedBack(UserFeedBack):
    datatype = "token_classification"

    def __init__(
        self,
        sample_uuid: str,
        name: str,
        delimiter: str,
        index_to_label: typing.Dict[int, str],
    ):
        super().__init__(sample_uuid)

        self._name = name
        self._delimiter = delimiter
        self._index_to_label = index_to_label

    def serialize(self) -> str:
        return json.dumps(
            {
                "delimiter": self._delimiter,
                "index_to_label": self._index_to_label,
            }
        )

    @staticmethod
    def deserialize(sample_uuid, name, repr) -> str:
        data = json.loads(repr)
        return TokenClassificationFeedBack(
            name=name,
            delimiter=data["delimiter"],
            index_to_label=data["index_to_label"],
            sample_uuid=sample_uuid,
        )


def deserialize_sample_datatype(
    type: str, unique_id: str, name: str, serialized_data: str
):
    if type == "text_classification":
        return TextClassificationSample.deserialize(
            name, serialized_data, unique_id=unique_id
        )

    if type == "token_classification":
        return TokenClassificationSample.deserialize(
            name, serialized_data, unique_id=unique_id
        )

    raise Exception(f"Cannot deserialize unknown sample type: {type}")


def deserialize_userfeedback(
    type: str, sample_uuid: str, name: str, serialized_data: str
):
    if type == "token_classification":
        return TokenClassificationFeedBack.deserialize(
            sample_uuid=sample_uuid, name=name, repr=serialized_data
        )

    raise Exception(f"Cannot deserialize unknown userfeedback type: {type}")
