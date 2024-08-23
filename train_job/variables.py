from __future__ import annotations

import ast
import html
import os
from dataclasses import MISSING, asdict, dataclass, field, fields
from enum import Enum
from typing import Dict, List, Optional, Type, TypeVar, Union, get_args, get_origin

from pydantic import root_validator

T = TypeVar("T", bound="EnvLoader")


class TypeEnum(str, Enum):
    NDB = "ndb"
    UDT = "udt"


class NDBSubType(str, Enum):
    shard_allocation = "shard_allocation"
    shard_train = "shard_train"
    single = "single"


class UDTSubType(str, Enum):
    text = "text"
    token = "token"


class RetrieverEnum(str, Enum):
    MACH = "mach"
    HYBRID = "hybrid"
    FINETUNABLE_RETRIEVER = "finetunable_retriever"


class EnvLoader:
    # Mapping of type names to Enum classes
    type_mapping = {
        "TypeEnum": TypeEnum,
        "NDBSubType": NDBSubType,
        "UDTSubType": UDTSubType,
        "RetrieverEnum": RetrieverEnum,
    }

    @classmethod
    def load_from_env(cls: Type[T]) -> T:
        """Load environment variables and return an instance of the class."""
        missing_vars = []
        env_vars: Dict[str, Optional[Union[str, int, float, bool]]] = {}

        for f in fields(cls):
            value = os.getenv(f.name.upper())
            if value is None or value.lower() == "none":
                if f.default is MISSING and f.default_factory is MISSING:
                    missing_vars.append(f.name.upper())
                else:
                    value = (
                        f.default if f.default is not MISSING else f.default_factory()
                    )
            else:
                value = cls._convert_type(value, f.type)
            env_vars[f.name] = value

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

        return cls(**env_vars)

    @staticmethod
    def _convert_type(
        value: str, field_type: Union[Type, str]
    ) -> Union[str, int, float, bool, None, Enum]:
        """Convert a string value to the specified field type."""
        if isinstance(field_type, str):
            field_type = EnvLoader.type_mapping.get(field_type, eval(field_type))

        origin = get_origin(field_type)
        args = get_args(field_type)

        if origin is Union:
            for arg in args:
                try:
                    return EnvLoader._convert_type(value, arg)
                except (ValueError, TypeError):
                    continue
            raise ValueError(f"Cannot convert {value} to any of {args}")

        if isinstance(field_type, type) and issubclass(field_type, Enum):
            try:
                # Try converting directly
                return field_type(value)
            except ValueError:
                # Handle case where value is in form 'EnumClass.EnumMember'
                enum_class, enum_member = value.split(".")
                enum_type = EnvLoader.type_mapping.get(enum_class)
                if enum_type and issubclass(enum_type, Enum):
                    return enum_type[enum_member]

        value = html.unescape(value)
        if field_type == bool:
            return ast.literal_eval(value.capitalize())
        if field_type == int:
            return int(value)
        if field_type == float:
            return float(value)
        if field_type == str:
            return value

        return ast.literal_eval(value)


def merge_dataclasses_to_dict(*instances) -> dict:
    """Merge multiple dataclass instances into a single dictionary."""
    result = {}
    for instance in instances:
        result.update(asdict(instance))
    return result


@dataclass
class GeneralVariables(EnvLoader):
    model_bazaar_dir: str
    license_key: str
    model_bazaar_endpoint: str
    model_id: str
    data_id: str
    base_model_id: Optional[str] = None
    type: TypeEnum = TypeEnum.NDB
    sub_type: Union[NDBSubType, UDTSubType] = NDBSubType.single


@dataclass
class TokenClassificationVariables(EnvLoader):
    target_labels: List[str] = None
    source_column: str = None
    target_column: str = None
    default_tag: str = None


@dataclass
class TextClassificationVariables(EnvLoader):
    delimiter: str = None
    text_column: str = None
    label_column: str = None
    n_target_classes: int = None


@dataclass
class MachVariables(EnvLoader):
    fhr: int = 50_000
    embedding_dim: int = 2048
    output_dim: int = 10_000
    extreme_num_hashes: int = 1
    hidden_bias: bool = False
    tokenizer: str = "char-4"


@dataclass
class VersionedEnvLoader(EnvLoader):
    version: str = "v1"

    def __post_init__(self):
        if self.version == "v1":
            # Automatically set on_disk and docs_on_disk to False if they exist
            if hasattr(self, "on_disk"):
                self.on_disk = False
            if hasattr(self, "docs_on_disk"):
                self.docs_on_disk = False


@dataclass
class FinetunableRetrieverVariables(VersionedEnvLoader):
    on_disk: bool = True


@dataclass
class NeuralDBVariables(VersionedEnvLoader):
    num_shards: int = 1
    num_models_per_shard: int = 1
    retriever: RetrieverEnum = RetrieverEnum.FINETUNABLE_RETRIEVER
    docs_on_disk: bool = True


@dataclass
class TrainVariables(EnvLoader):
    type: TypeEnum = TypeEnum.NDB
    learning_rate: float = 0.005
    max_in_memory_batches: Optional[int] = None
    batch_size: int = 2048
    unsupervised_epochs: int = 5
    supervised_epochs: int = 3
    unsupervised_train: bool = True
    disable_finetunable_retriever: bool = True
    fast_approximation: bool = True
    checkpoint_interval: Optional[int] = None
    metrics: List[str] = field(default_factory=lambda: ["loss"])
    validation_metrics: List[str] = field(
        default_factory=lambda: ["categorical_accuracy"]
    )
    num_buckets_to_sample: Optional[int] = None

    def __post_init__(self):
        if self.type == TypeEnum.NDB:
            self.metrics = ["hash_precision@1", "loss"]
        elif self.type == TypeEnum.UDT:
            self.metrics = ["precision@1", "loss"]
            self.validation_metrics = ["categorical_accuracy", "recall@1"]


@dataclass
class S3Variables(EnvLoader):
    aws_access_key: Optional[str] = None
    aws_secret_access_key: Optional[str] = None


@dataclass
class ComputeVariables(EnvLoader):
    model_cores: Optional[int] = None
    model_memory: Optional[int] = None
    priority: Optional[int] = None


@dataclass
class ShardVariables(EnvLoader):
    shard_num: int
    num_classes: int


@dataclass
class CSVDocumentVariables(EnvLoader):
    csv_id_column: str = None
    csv_strong_columns: list[str] = None
    csv_weak_columns: list[str] = None
    csv_reference_columns: list[str] = None
