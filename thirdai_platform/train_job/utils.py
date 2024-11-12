import logging
import os
import shutil
import sys
from pathlib import Path
from typing import List

from platform_common.pydantic_models.training import FileInfo, FileLocation
from thirdai import neural_db as ndb

GB_1 = 1024 * 1024 * 1024  # Define 1 GB in bytes


def check_csv_only(all_files: List[FileInfo]):
    for file in all_files:
        if file.ext() != ".csv":
            raise ValueError(
                "Only CSV files are supported for supervised training and test."
            )


def check_local_nfs_only(files: List[FileInfo]):
    for file in files:
        if file.location != FileLocation.local and file.location != FileLocation.nfs:
            raise ValueError(
                "Only local/nfs files are supported for supervised training/test."
            )


def check_disk(db, model_bazaar_dir: str, files: List[FileInfo]):
    """
    Check if there is enough disk space to process the files.
    """
    approx_ndb_size = 1.5 * sys.getsizeof(db) + 2 * sum(
        [os.path.getsize(file.path) for file in files if os.path.exists(file.path)]
    )

    available_nfs_storage = shutil.disk_usage(
        os.path.join(model_bazaar_dir, "models")
    ).free

    if available_nfs_storage < approx_ndb_size:
        critical_message = f"Available NFS storage : {available_nfs_storage/GB_1} GB is less than approx model size : {approx_ndb_size/GB_1} GB."
        logging.critical(critical_message)
        raise Exception(critical_message)


def convert_supervised_to_ndb_file(file: FileInfo) -> ndb.Sup:
    """
    Convert a supervised training file to an NDB file.
    """
    if file.ext() == ".csv":
        return ndb.Sup(
            file.path,
            query_column=file.options.get("csv_query_column", None),
            id_delimiter=file.options.get("csv_id_delimiter", None),
            id_column=file.options.get("csv_id_column", None),
            source_id=file.doc_id,
        )
    else:
        raise TypeError(
            f"{file.ext()} file type is not supported for supervised training, only .csv files are supported."
        )


def get_directory_size(directory: Path) -> int:
    """
    Calculate the size of a directory in bytes.
    """
    size = 0
    for root, dirs, files in os.walk(directory):
        for name in files:
            size += os.stat(Path(root) / name).st_size
    return size
