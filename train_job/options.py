from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


class ModelType(str, Enum):
    NDB = "ndb"
    UDT = "udt"


class FileInfo(BaseModel):
    path: str
    doc_id: Optional[str] = None
    options: Dict[str, Any] = {}
    metadata: Optional[Dict[str, Any]] = None


class MachOptions(BaseModel):
    fhr: int = 50_000
    embedding_dim: int = 2048
    output_dim: int = 10_000
    extreme_num_hashes: int = 1
    hidden_bias: bool = False
    tokenizer: str = "char-4"
    unsupervised_epochs: int = 5
    supervised_epochs: int = 3
    metrics: List[str] = ["hash_precision@1", "loss"]


class NDBVersion(str, Enum):
    v1 = "v1"
    v2 = "v2"


class RetrieverType(str, Enum):
    mach = "mach"
    hybrid = "hybrid"
    finetunable_retriever = "finetunable_retriever"


class NDBv1Options(BaseModel):
    version: Literal[NDBVersion.v1]

    retriever: RetrieverType = RetrieverType.finetunable_retriever

    mach_options: Optional[MachOptions] = None
    checkpoint_interval: Optional[int] = None

    @model_validator(mode="after")
    def check_mach_options(self):
        if (
            self.retriever != RetrieverType.finetunable_retriever
            and not self.mach_options
        ) or (
            self.retriever == RetrieverType.finetunable_retriever and self.mach_options
        ):
            raise ValueError("mach_options must be provided if using mach or hybrid")


class NDBv2Options(BaseModel):
    version: Literal[NDBVersion.v2]

    on_disk: bool = True


class NDBOptions(BaseModel):
    model_type: Literal[ModelType.NDB]

    version_options: Union[NDBv1Options, NDBv2Options] = Field(
        ..., discriminator="version"
    )

    unsupervised_files: List[FileInfo]
    supervised_files: List[FileInfo] = []
    test_files: List[FileInfo] = []


class UDTSubType(str, Enum):
    text = "text"
    token = "token"


class TokenClassificationOptions(BaseModel):
    udt_sub_type: Literal[UDTSubType.token]

    target_labels: List[str] = None
    source_column: str = None
    target_column: str = None
    default_tag: str = None


class TextClassificationOptions(BaseModel):
    udt_sub_type: Literal[UDTSubType.text]

    delimiter: str = None
    text_column: str = None
    label_column: str = None
    n_target_classes: int = None


class UDTTrainOptions(BaseModel):
    supervised_epochs: int = 3
    learning_rate: float = 0.005
    batch_size: int = 2048
    max_in_memory_batches: Optional[int] = None

    metrics: List[str] = ["precision@1", "loss"]
    validation_metrics: List[str] = ["categorical_accuracy", "recall@1"]


class UDTOptions(BaseModel):
    model_type: Literal[ModelType.UDT]

    udt_options: Union[TokenClassificationOptions, TextClassificationOptions] = Field(
        ..., discriminator="udt_sub_type"
    )

    train_files: List[FileInfo]
    test_files: List[FileInfo] = []

    train_options: UDTTrainOptions = UDTTrainOptions()


class BaseOptions(BaseModel):
    model_bazaar_dir: str
    license_key: str
    model_bazaar_endpoint: str
    model_id: str
    data_id: str
    base_model_id: Optional[str] = None

    model_options: Union[NDBOptions, UDTOptions] = Field(
        ..., discriminator="model_type"
    )
