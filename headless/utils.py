import os
import re
import sys
import warnings
from typing import Any, Callable, Dict, List, Optional, Type

import boto3
from botocore import UNSIGNED
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from thirdai import neural_db as ndb

from headless.configs import Config


def get_csv_source_id(
    file: str,
    CSV_ID_COLUMN: Optional[str] = None,
    CSV_STRONG_COLUMNS: Optional[List[str]] = None,
    CSV_WEAK_COLUMNS: Optional[List[str]] = None,
    CSV_REFERENCE_COLUMNS: Optional[List[str]] = None,
    CSV_METADATA: Optional[Dict[str, str]] = None,
) -> str:
    """
    Returns the source ID for a CSV file.

    Parameters:
    file (str): Path to the CSV file.
    CSV_ID_COLUMN (str, optional): Column name for IDs.
    CSV_STRONG_COLUMNS (list[str], optional): List of strong columns.
    CSV_WEAK_COLUMNS (list[str], optional): List of weak columns.
    CSV_REFERENCE_COLUMNS (list[str], optional): List of reference columns.
    CSV_METADATA (dict[str, str], optional): Metadata for the CSV file.

    Returns:
    str: The hash ID of the CSV source.

    Raises:
    TypeError: If the file type is not supported.
    """
    _, ext = os.path.splitext(file)

    if ext == ".csv":
        return ndb.CSV(
            file,
            id_column=CSV_ID_COLUMN,
            strong_columns=CSV_STRONG_COLUMNS,
            weak_columns=CSV_WEAK_COLUMNS,
            reference_columns=CSV_REFERENCE_COLUMNS,
            metadata=CSV_METADATA,
        ).hash
    else:
        raise TypeError(f"{ext} Document type isn't supported.")


def get_configs(config_type: type, config_regex: str) -> List[Config]:
    """
    Retrieves a list of configuration subclasses that match a given regex pattern.

    Parameters:
    config_type (type): The base configuration class type.
    config_regex (str): Regular expression to filter configuration names.

    Returns:
    list[Config]: List of matching configuration subclasses.

    Raises:
    Warning: If no configurations match the regex pattern.
    """
    configs = [config for config in config_type.__subclasses__()]
    config_re = re.compile(config_regex)
    configs = list(
        filter(
            lambda config: config.name is not None and config_re.match(config.name),
            configs,
        )
    )
    if len(configs) == 0:
        warnings.warn(
            f"Couldn't match regular expression '{config_regex}' to any configs"
        )

    return configs


def extract_static_methods(cls: Type) -> Dict[str, Callable]:
    """
    Extracts all static methods from a given class and returns them in a dictionary.

    Args:
        cls (Type): The class to extract static methods from.

    Returns:
        Dict[str, Callable]: A dictionary with method names as keys and static methods as values.
    """
    static_methods = {}
    for name, method in cls.__dict__.items():
        if isinstance(method, staticmethod):
            static_methods[name] = method.__func__
    return static_methods


def download_from_s3_if_not_exists(s3_uri, local_dir):
    from botocore.client import Config

    if not os.path.exists(local_dir):
        os.makedirs(local_dir)

    config = Config(
        signature_version=UNSIGNED,
        retries={"max_attempts": 10, "mode": "standard"},
        connect_timeout=5,
        read_timeout=60,
    )

    s3 = boto3.client("s3", config=config)
    bucket_name = s3_uri.split("/")[2]
    s3_path = "/".join(s3_uri.split("/")[3:])

    try:
        for key in s3.list_objects_v2(Bucket=bucket_name, Prefix=s3_path)["Contents"]:
            local_file_path = os.path.join(local_dir, key["Key"].split("/")[-1])
            if not os.path.exists(local_file_path):
                s3.download_file(bucket_name, key["Key"], local_file_path)
                print(f"Downloaded {local_file_path}")
    except (NoCredentialsError, PartialCredentialsError) as e:
        print(f"Error in downloading from S3: {str(e)}")
        sys.exit(1)


def normalize_s3_uri(s3_uri):
    return s3_uri.rstrip("/")
