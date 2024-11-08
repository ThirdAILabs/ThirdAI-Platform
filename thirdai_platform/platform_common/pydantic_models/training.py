import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from platform_common.pydantic_models.cloud_credentials import (
    AWSCredentials,
    AzureCredentials,
    CloudCredentials,
    CredentialRegistry,
    GCPCredentials,
)
from platform_common.thirdai_storage.data_types import (
    LabelEntity,
    TokenClassificationData,
)
from pydantic import BaseModel, Field, model_validator


class ModelType(str, Enum):
    NDB = "ndb"
    UDT = "udt"
    ENTERPRISE_SEARCH = "enterprise-search"


class ModelDataType(str, Enum):
    NDB = "ndb"
    UDT = "udt"
    UDT_DATAGEN = "udt_datagen"


class FileLocation(str, Enum):
    local = "local"
    nfs = "nfs"
    s3 = "s3"
    azure = "azure"
    gcp = "gcp"


class FileInfo(BaseModel):
    path: str
    location: FileLocation
    doc_id: Optional[str] = None
    options: Dict[str, Any] = {}
    metadata: Optional[Dict[str, Any]] = None
    cloud_credentials: Optional[CloudCredentials] = None

    def __init__(self, **data):
        super().__init__(**data)
        if not self.cloud_credentials:
            self.cloud_credentials = self.get_relevant_credentials(
                location=self.location
            )

    def get_relevant_credentials(self, location: str) -> Optional[CloudCredentials]:
        """Initialize only the relevant credentials based on the location."""
        if location == FileLocation.s3.value:
            return CloudCredentials(aws=AWSCredentials())
        elif location == FileLocation.azure.value:
            return CloudCredentials(azure=AzureCredentials())
        elif location == FileLocation.gcp.value:
            return CloudCredentials(gcp=GCPCredentials())
        return None  # No credentials needed for local or nfs locations

    def ext(self) -> str:
        _, ext = os.path.splitext(self.path)
        return ext

    def extract_bucket_name(self) -> Optional[str]:
        """Extracts the bucket name based on the storage location."""
        if self.location == FileLocation.s3:
            return self.parse_s3_url()[0]
        elif self.location == FileLocation.azure:
            return self.parse_azure_url()[0]
        elif self.location == FileLocation.gcp:
            return self.parse_gcp_url()[0]
        return None

    def parse_s3_url(self):
        """
        Parses an S3 URL and returns the bucket name and key.
        Only works for FileInfo objects where location is S3.

        Returns:
            tuple: (bucket_name, key) where bucket_name is the name of the S3 bucket
                   and key is the path within the bucket.
        """
        if self.location != FileLocation.s3:
            raise ValueError(
                f"Invalid operation. File location is not S3: {self.location}"
            )

        if not self.path.startswith("s3://"):
            raise ValueError(f"Invalid S3 URL: {self.path}")

        # Remove the 's3://' prefix and split the remaining string
        s3_path = self.path[5:]  # Remove 's3://'
        bucket_name, _, key = s3_path.partition("/")

        return bucket_name, key

    def parse_azure_url(self):
        """
        Parses an Azure Blob Storage URL and returns the container name and blob path.
        Only works for FileInfo objects where location is Azure.

        Returns:
            tuple: (container_name, blob_path) where container_name is the name of the
                   Azure container and blob_path is the path to the blob inside the container.
        """
        if self.location != FileLocation.azure:
            raise ValueError(
                f"Invalid operation. File location is not Azure: {self.location}"
            )

        if not self.path.startswith("https://"):
            raise ValueError(f"Invalid Azure Blob URL: {self.path}")

        # Azure Blob URLs follow the pattern: https://<account_name>.blob.core.windows.net/<container>/<blob_path>
        url_parts = self.path.split("/")

        if len(url_parts) < 4:
            raise ValueError(f"Invalid Azure Blob URL structure: {self.path}")

        container_name = url_parts[
            3
        ]  # After 'https://<account_name>.blob.core.windows.net/'
        blob_path = "/".join(url_parts[4:])  # Remaining path as the blob key

        return container_name, blob_path

    def parse_gcp_url(self):
        """
        Parses a GCP Cloud Storage URL and returns the bucket name and key.
        Only works for FileInfo objects where location is GCP.

        Returns:
            tuple: (bucket_name, key) where bucket_name is the name of the GCP bucket
                   and key is the path within the bucket.
        """
        if self.location != FileLocation.gcp:
            raise ValueError(
                f"Invalid operation. File location is not GCP: {self.location}"
            )

        if not self.path.startswith("gs://"):
            raise ValueError(f"Invalid GCP URL: {self.path}")

        gcs_path = self.path[5:]  # Remove 'gs://'
        bucket_name, _, key = gcs_path.partition("/")

        return bucket_name, key


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
    advanced_search: bool = False


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

    deletions: List[str] = []

    class Config:
        protected_namespaces = ()

    @model_validator(mode="after")
    def check_nonempty(self):
        if len(self.unsupervised_files) + len(self.supervised_files) == 0:
            raise ValueError(
                "Unsupervised or supervised files must not be non empty for NDB training."
            )
        return self

    def get_files(self):
        return self.unsupervised_files + self.supervised_files + self.test_files


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

    def get_files(self):
        return self.supervised_files + self.test_files


class UDTGeneratedData(BaseModel):
    model_data_type: Literal[ModelDataType.UDT_DATAGEN] = ModelDataType.UDT_DATAGEN
    secret_token: str

    class Config:
        protected_namespaces = ()

    def get_files(self):
        return []


class LLMProvider(str, Enum):
    openai = "openai"
    cohere = "cohere"


class TextClassificationDatagenOptions(BaseModel):
    sub_type: Literal[UDTSubType.text] = UDTSubType.text
    samples_per_label: int
    target_labels: List[LabelEntity]
    user_vocab: Optional[List[str]] = None
    user_prompts: Optional[List[str]] = None
    vocab_per_sentence: int = 4


class TokenClassificationDatagenOptions(BaseModel):
    sub_type: Literal[UDTSubType.token] = UDTSubType.token
    tags: List[LabelEntity]
    num_sentences_to_generate: int = 10_000
    num_samples_per_tag: Optional[int] = None

    # example NER samples
    samples: Optional[List[TokenClassificationData]] = None
    templates_per_sample: int = 10

    @model_validator(mode="after")
    def deduplicate_tags(cls, values):
        tag_map = {}
        for tag in values.tags:
            key = tag.name
            if key in tag_map:
                tag_map[key].examples = list(
                    set(tag_map[key].examples) | set(tag.examples)
                )
            else:
                tag_map[key] = tag
        values.tags = list(tag_map.values())
        return values


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

    is_retraining: bool = False

    class Config:
        protected_namespaces = ()

    @model_validator(mode="after")
    def check_model_data_match(self):
        if self.model_options.model_type.value not in self.data.model_data_type.value:
            raise ValueError("Model and data fields don't match")
        return self

    def save_train_config(self):
        config_path = os.path.join(
            self.model_bazaar_dir, "models", str(self.model_id), "train_config.json"
        )
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as file:
            file.write(self.model_dump_json(indent=4))

        return config_path

    def populate_credential_registry_and_save(self, registry_path: Path):
        """
        Populate the credential registry with credentials for each bucket.
        """
        registry = CredentialRegistry()

        all_files = self.data.get_files()

        for file_info in all_files:
            bucket_name = file_info.extract_bucket_name()
            if bucket_name and file_info.cloud_credentials:
                registry.save_credentials(bucket_name, file_info.cloud_credentials)

        registry.save_to_disk(registry_path=registry_path)
