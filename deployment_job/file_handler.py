import os
from typing import List, Optional, Dict, Any

import boto3
from botocore import UNSIGNED
from botocore.client import Config
from fastapi import UploadFile
from pydantic import BaseModel
from enum import Enum


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


def download_local_file(file_info: FileInfo, upload_file: UploadFile, dest_dir: str):
    assert os.path.basename(file_info.path) == upload_file.filename
    destination_path = os.path.join(dest_dir, upload_file.filename)
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    with open(destination_path, "wb") as f:
        f.write(upload_file.file.read())
    upload_file.file.close()
    return destination_path


def download_local_files(
    files: List[UploadFile], file_infos: List[FileInfo], dest_dir: str
) -> List[FileInfo]:
    filename_to_file = {file.filename: file for file in files}

    os.makedirs(dest_dir, exist_ok=True)

    all_files = []
    for file_info in file_infos:
        if file_info.location == FileLocation.local:
            try:
                local_path = download_local_file(
                    file_info=file_info,
                    upload_file=filename_to_file[os.path.basename(file_info.path)],
                    dest_dir=dest_dir,
                )
            except Exception as error:
                raise ValueError(
                    f"Error processing file '{file_info.path}' from '{file_info.location}': {error}"
                )
            all_files.append(
                FileInfo(
                    path=local_path,
                    location=file_info.location,
                    doc_id=file_info.doc_id,
                    options=file_info.options,
                    metadata=file_info.metadata,
                )
            )
        else:
            all_files.append(file_info)

    return all_files


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
