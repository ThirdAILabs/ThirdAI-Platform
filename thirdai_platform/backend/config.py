import os
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


class ModelType(str, Enum):
    NDB = "ndb"
    UDT = "udt"


class ModelDataType(str, Enum):
    NDB = "ndb"
    UDT = "udt"
    UDT_DATAGEN = "udt_datagen"


class FileLocation(str, Enum):
    local = "local"
    nfs = "nfs"
    s3 = "s3"


class FileInfo(BaseModel):
    path: str
    location: FileLocation
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


class NDBSubType(str, Enum):
    v1 = "v1"
    v2 = "v2"


class RetrieverType(str, Enum):
    mach = "mach"
    hybrid = "hybrid"
    finetunable_retriever = "finetunable_retriever"


class NDBv1Options(BaseModel):
    ndb_sub_type: Literal[NDBSubType.v1] = NDBSubType.v1

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
            raise ValueError(
                "mach_options must be provided if using mach or hybrid, and must not be provided if using finetunable_retriever"
            )
        return self


class NDBv2Options(BaseModel):
    ndb_sub_type: Literal[NDBSubType.v2] = NDBSubType.v2

    on_disk: bool = True


class NDBOptions(BaseModel):
    model_type: Literal[ModelType.NDB] = ModelType.NDB

    ndb_options: Union[NDBv1Options, NDBv2Options] = Field(
        NDBv2Options(), discriminator="ndb_sub_type"
    )

    class Config:
        protected_namespaces = ()


class NDBData(BaseModel):
    model_data_type: Literal[ModelDataType.NDB] = ModelDataType.NDB

    unsupervised_files: List[FileInfo] = []
    supervised_files: List[FileInfo] = []
    test_files: List[FileInfo] = []

    class Config:
        protected_namespaces = ()

    @model_validator(mode="after")
    def check_nonempty(self):
        if len(self.unsupervised_files) + len(self.supervised_files) == 0:
            raise ValueError(
                "Unsupervised or supervised files must not be non empty for NDB training."
            )
        return self


class UDTSubType(str, Enum):
    text = "text"
    token = "token"


class TokenClassificationOptions(BaseModel):
    udt_sub_type: Literal[UDTSubType.token] = UDTSubType.token

    target_labels: List[str]
    source_column: str
    target_column: str
    default_tag: str = "O"


class TextClassificationOptions(BaseModel):
    udt_sub_type: Literal[UDTSubType.text] = UDTSubType.text

    text_column: str
    label_column: str
    n_target_classes: int
    delimiter: str = ","


class UDTTrainOptions(BaseModel):
    supervised_epochs: int = 3
    learning_rate: float = 0.005
    batch_size: int = 2048
    max_in_memory_batches: Optional[int] = None

    metrics: List[str] = ["precision@1", "loss"]
    validation_metrics: List[str] = ["categorical_accuracy", "recall@1"]


class UDTOptions(BaseModel):
    model_type: Literal[ModelType.UDT] = ModelType.UDT

    udt_options: Union[TokenClassificationOptions, TextClassificationOptions] = Field(
        ..., discriminator="udt_sub_type"
    )

    train_options: UDTTrainOptions = UDTTrainOptions()

    class Config:
        protected_namespaces = ()


class UDTData(BaseModel):
    model_data_type: Literal[ModelDataType.UDT] = ModelDataType.UDT

    supervised_files: List[FileInfo]
    test_files: List[FileInfo] = []

    class Config:
        protected_namespaces = ()

    @model_validator(mode="after")
    def check_nonempty(self):
        if len(self.supervised_files) == 0:
            raise ValueError("Supervised files must not be empty for UDT training.")
        return self


class UDTGeneratedData(BaseModel):
    model_data_type: Literal[ModelDataType.UDT_DATAGEN] = ModelDataType.UDT_DATAGEN
    secret_token: str


class LLMProvider(str, Enum):
    openai = "openai"
    cohere = "cohere"


class TextClassificationDatagenOptions(BaseModel):
    sub_type: Literal[UDTSubType.text] = UDTSubType.text

    samples_per_label: int
    target_labels: List[str]
    examples: Dict[str, List[str]]
    labels_description: Dict[str, str]
    user_vocab: Optional[List[str]] = None
    user_prompts: Optional[List[str]] = None
    vocab_per_sentence: int = 4


class TokenClassificationDatagenOptions(BaseModel):
    sub_type: Literal[UDTSubType.token] = UDTSubType.token

    domain_prompt: str
    tags: List[str]
    tag_examples: Dict[str, List[str]]
    num_sentences_to_generate: int
    num_samples_per_tag: int = 4


class DatagenOptions(BaseModel):
    task_prompt: str
    llm_provider: LLMProvider = LLMProvider.openai

    datagen_options: Union[
        TokenClassificationDatagenOptions, TextClassificationDatagenOptions
    ] = Field(..., discriminator="sub_type")


class JobOptions(BaseModel):
    allocation_cores: int = Field(1, gt=0)
    allocation_memory: int = Field(6800, gt=500)


class TrainConfig(BaseModel):
    model_bazaar_dir: str
    license_key: str
    model_bazaar_endpoint: str
    model_id: str
    data_id: str
    base_model_id: Optional[str] = None

    # The model and data fields are separate because the model_options are designed
    # to be passed directly from the parameters supplied to the train endpoint to
    # the train config without requiring additional processing. The data may require
    # some processing, to download files, copy to directories, etc. Thus they are separated
    # so that the model options can be passed through while the data is processed
    # in the train endpoint.
    model_options: Union[NDBOptions, UDTOptions] = Field(
        ..., discriminator="model_type"
    )
    datagen_options: Optional[DatagenOptions] = None
    job_options: JobOptions

    data: Union[NDBData, UDTData, UDTGeneratedData] = Field(
        ..., discriminator="model_data_type"
    )

    class Config:
        protected_namespaces = ()

    @model_validator(mode="after")
    def check_model_data_match(self):
        if self.model_options.model_type.value not in self.data.model_data_type.value:
            raise ValueError("Model and data fields don't match")
        return self
