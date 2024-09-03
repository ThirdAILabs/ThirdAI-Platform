import os
import sys
from abc import ABC
from typing import Optional

base_path = os.getenv("SHARE_DIR")
if not base_path:
    print("Error: SHARE_DIR environment variable is not set.")
    sys.exit(1)


class Config(ABC):
    """
    Abstract base class for configuration settings.

    Attributes:
    name (str): Name of the configuration.
    base_path (str): Base path for data storage.
    doc_type (str): Type of documents (e.g., local, nfs).
    nfs_original_base_path (str): Base path for NFS storage.
    unsupervised_paths (list[str]): List of paths to unsupervised data files.
    supervised_paths (list[str]): List of paths to supervised data files.
    test_paths (list[str]): List of paths to test data files.
    insert_paths (list[str]): List of paths to insert data files.
    id_column (str): Column name for ID.
    strong_columns (list[str]): List of strong columns for data.
    weak_columns (list[str]): List of weak columns for data.
    reference_columns (list[str]): List of reference columns for data.
    query_column (str): Column name for queries.
    id_delimiter (str): Delimiter used in IDs.
    model_cores (int): Number of cores used for single model (Used for sharded training).
    model_memory (int): Amount of memory allocated for the model (in MB) (Used for sharded training).
    input_dim (int): Input dimension for the model.
    hidden_dim (int): Hidden dimension for the model.
    output_dim (int): Output dimension for the model.
    allocation_memory (int): Memory allocation for the model (in MB) (Used for shard allocation or single training).
    allocation_cores (int): Number of cores allocated for model training (Used for shard allocation or single training).
    epochs (int): Number of training epochs.
    retriever (str): Type of retriever used (e.g., hybrid, mach).
    checkpoint_interval (int): Interval for saving model checkpoints.
    sub_type (str): Sub-type of the configuration.
    n_classes (Optional[int]): Number of classes for classification tasks.
    target_labels (Optional[list[str]]): List of target labels for token classification.
    """

    name: str = None

    base_path: str = base_path
    doc_type: str = "local"
    nfs_original_base_path: str = "/opt/neuraldb_enterprise/"
    unsupervised_paths: list[str] = []
    supervised_paths: list[str] = []
    test_paths: list[str] = []
    insert_paths: list[str] = []

    id_column: str = None
    strong_columns: list[str] = None
    weak_columns: list[str] = None
    reference_columns: list[str] = None
    query_column: str = None
    id_delimiter: str = None

    model_cores: int = 2
    model_memory: int = 2000
    input_dim: int = 10000
    hidden_dim: int = 1024
    output_dim: int = 5000
    allocation_memory: int = 5000
    allocation_cores: int = 4
    checkpoint_interval: int = 1

    epochs: int = 3

    retriever: str = "finetunable_retriever"

    sub_type: str = "text"
    n_classes: Optional[int] = None
    target_labels: list[str] = None


class Scifact(Config):
    """
    Configuration settings for the Scifact dataset.
    """

    name: str = "scifact"

    unsupervised_paths: list[str] = [
        "scifact/unsupervised_part1.csv",
        "scifact/unsupervised_part2.csv",
    ]
    supervised_paths: list[str] = [
        "scifact/trn_supervised_part1.csv",
        "scifact/trn_supervised_part2.csv",
    ]
    test_paths: list[str] = [
        "scifact/tst_supervised.csv",
    ]
    insert_paths: list[str] = ["scifact/sample_nda.pdf"]

    strong_columns: list[str] = ["TITLE"]
    weak_columns: list[str] = ["TEXT"]
    reference_columns: list[str] = ["TITLE", "TEXT"]
    id_column: str = "DOC_ID"
    query_column: str = "QUERY"
    id_delimiter: str = ":"


class Text(Config):
    """
    Configuration settings for text data.
    """

    name: str = "text"

    unsupervised_paths: list[str] = ["clinc/train.csv"]
    id_column: str = "category"
    query_column: str = "text"
    n_classes: int = 150

    sub_type: str = "text"


class Token(Config):
    """
    Configuration settings for token data.
    """

    name: str = "token"

    unsupervised_paths: list[str] = ["token/ner.csv"]
    id_column: str = "target"
    query_column: str = "source"

    target_labels: list[str] = ["PER", "ORG"]
    sub_type: str = "token"


class Dummy(Config):
    """
    Config for tests which doesnot needs a training config
    """

    name: str = "dummy"
