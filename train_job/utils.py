import os
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
from botocore import UNSIGNED
from botocore.client import Config
from config import FileInfo, FileLocation
from fastapi import Response
from thirdai import neural_db as ndb

GB_1 = 1024 * 1024 * 1024  # Define 1 GB in bytes


def create_s3_client() -> boto3.client:
    """
    Create and return an S3 client using environment variables.
    """
    aws_access_key = os.getenv("AWS_ACCESS_KEY")
    aws_secret_access_key = os.getenv("AWS_ACCESS_SECRET")

    config_params = {
        "retries": {"max_attempts": 10, "mode": "standard"},
        "connect_timeout": 5,
        "read_timeout": 60,
    }

    if not aws_access_key or not aws_secret_access_key:
        config_params["signature_version"] = UNSIGNED
        s3_client = boto3.client("s3", config=Config(**config_params))
    else:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_access_key,
            config=Config(**config_params),
        )

    return s3_client


def list_s3_files(path: str):
    s3_client = create_s3_client()

    bucket_name, prefix = path.replace("s3://", "").split("/", 1)
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

    file_keys = []
    for page in pages:
        if "Contents" in page:
            for obj in page["Contents"]:
                file_keys.append(f"s3://{bucket_name}/{obj['Key']}")

    return file_keys


def expand_file_info(paths: List[str], file_info: FileInfo):
    return [
        FileInfo(
            path=path,
            location=file_info.location,
            doc_id=file_info.doc_id if len(paths) == 1 else None,
            options=file_info.options,
            metadata=file_info.metadata,
        )
        for path in paths
    ]


def list_files_in_nfs_dir(path: str):
    if os.path.isdir(path):
        return [
            os.path.join(root, file)
            for root, _, files_in_dir in os.walk(path)
            for file in files_in_dir
        ]
    return [path]


def expand_s3_buckets_and_directories(file_infos: List[FileInfo]) -> List[FileInfo]:
    """
    This function takes in a list of file infos and expands it so that each file info
    represents a single file that can be passed to NDB or UDT. This is because we allow
    users to specify s3 buckets or nfs directories in train, that could contain multiple
    files, however UDT only accepts single files, and we need the individual docs themselves
    so that we can parallelize doc parsing in NDB. If one of the input file infos
    is an s3 bucket with N documents in it, then this will replace it with N file infos,
    one per document in the bucket.
    """
    expanded_files = []
    for file_info in file_infos:
        if file_info.location == FileLocation.local:
            expanded_files.append(file_info)
        elif file_info.location == FileLocation.s3:
            s3_objects = list_s3_files(file_info.path)
            expanded_files.extend(
                expand_file_info(paths=s3_objects, file_info=file_info)
            )
        elif file_info.location == FileLocation.nfs:
            directory_files = list_files_in_nfs_dir(file_info.path)
            expanded_files.extend(
                expand_file_info(paths=directory_files, file_info=file_info)
            )
    return expanded_files


def check_csv_only(all_files: List[FileInfo]):
    for file in all_files:
        _, ext = os.path.splitext(file.path)
        if ext != ".csv":
            raise ValueError(
                "Only CSV files are supported for supervised training and test."
            )


def convert_to_ndb_file(
    file: str, metadata: Optional[Dict[str, Any]], options: Dict[str, Any]
) -> ndb.Document:
    """
    Convert a file to an NDB file type based on its extension.
    """
    filename, ext = os.path.splitext(file)

    if ext == ".pdf":
        return ndb.PDF(file, metadata=metadata, save_extra_info=False)
    elif ext == ".docx":
        return ndb.DOCX(file, metadata=metadata)
    elif ext == ".html":
        base_filename = os.path.basename(filename)

        with open(file, "r", encoding="utf-8") as f:
            html_content = f.read()

        dummy_response = Response()
        dummy_response.status_code = 200
        dummy_response._content = html_content.encode("utf-8")

        return ndb.URL(
            base_filename, dummy_response, metadata=metadata, save_extra_info=False
        )
    elif ext == ".csv":
        return ndb.CSV(
            file,
            id_column=options.get("csv_id_column", None),
            strong_columns=options.get("csv_strong_columns", None),
            weak_columns=options.get("csv_weak_columns", None),
            reference_columns=options.get("csv_reference_columns", None),
            metadata=metadata,
            save_extra_info=False,
        )
    else:
        raise TypeError(f"{ext} Document type isn't supported yet.")


def process_file(doc: FileInfo, tmp_dir: str) -> ndb.Document:
    """
    Process a file, downloading it from S3 if necessary, and convert it to an NDB file.
    """
    if doc.path.startswith("s3://"):
        s3 = True
        s3_client = create_s3_client()
        bucket_name, prefix = doc.path.replace("s3://", "").split("/", 1)
        local_file_path = os.path.join(tmp_dir, os.path.basename(prefix))

        # Download the file from S3
        try:
            s3_client.download_file(bucket_name, prefix, local_file_path)
        except Exception as error:
            print(
                f"There was an error downloading the file from s3 : {error}. {doc.path}"
            )
            return f"There was an error downloading the file from s3 : {error}"
    else:
        local_file_path = doc.path
        s3 = False

    # Convert to NDB file
    ndb_file = convert_to_ndb_file(
        local_file_path, metadata=doc.metadata, options=doc.options
    )

    if s3:
        ndb_file.path = Path(f"/{bucket_name}.s3.amazonaws.com/{prefix}")
        # Remove the local file
        os.remove(local_file_path)

    return ndb_file


def producer(files: List[FileInfo], buffer, tmp_dir: str):
    """
    Process files in parallel and add the resulting NDB files to a buffer.
    """
    max_cores = os.cpu_count()
    num_workers = max(1, max_cores - 6)
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_file = {
            executor.submit(process_file, file, tmp_dir): file for file in files
        }

        for future in as_completed(future_to_file):
            file = future_to_file[future]
            try:
                ndb_file = future.result()
                if ndb_file and not isinstance(ndb_file, str):
                    buffer.put(ndb_file)
                    print(f"Successfully processed {file.path}", flush=True)
            except Exception as e:
                print(f"Error processing file {file}: {e}")

    buffer.put(None)  # Signal that the producer is done


def consumer(buffer, db, epochs: int = 5, batch_size: int = 10):
    """
    Consume NDB files from a buffer and insert them into NeuralDB in batches.
    """
    batch = []

    while True:
        ndb_doc = buffer.get()
        if ndb_doc is None:
            # Process any remaining documents in the last batch
            if batch:
                db.insert(batch, train=True, epochs=epochs)
            break

        batch.append(ndb_doc)

        # Process the batch if it reaches the batch size
        if len(batch) >= batch_size and buffer.qsize() == 0:
            db.insert(batch, train=True, epochs=epochs)
            batch.clear()


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
        print(
            f"Available NFS storage : {available_nfs_storage/GB_1} GB is less than approx model size : {approx_ndb_size/GB_1} GB."
        )
        raise Exception("Training aborted due to low disk space.")


def convert_supervised_to_ndb_file(file: FileInfo) -> ndb.Sup:
    """
    Convert a supervised training file to an NDB file.
    """
    _, ext = os.path.splitext(file.path)
    if ext == ".csv":
        return ndb.Sup(
            file.path,
            query_column=file.options.get("csv_query_column", None),
            id_delimiter=file.options.get("csv_id_delimiter", None),
            id_column=file.options.get("csv_id_column", None),
            source_id=file.doc_id,
        )
    else:
        raise TypeError(
            f"{ext} file type is not supported for supervised training, only .csv files are supported."
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
