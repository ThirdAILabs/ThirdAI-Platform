import json
import os
from abc import ABC, abstractmethod
from typing import List

import boto3
from backend.train_config import FileInfo, FileLocation
from fastapi import HTTPException, UploadFile, status


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


class S3StorageHandler:
    """
    S3 storage handler for processing and validating S3 files.
    Methods:
    - create_s3_client: Creates an S3 client.
    - process_files: Processes and saves the S3 file.
    - list_s3_files: Lists files in the specified S3 location.
    - validate_file: Validates the S3 file.
    """

    def __init__(self):
        self.s3_client = self.create_s3_client()

    def create_s3_client(self):
        from botocore import UNSIGNED
        from botocore.client import Config

        aws_access_key = os.getenv("AWS_ACCESS_KEY")
        aws_secret_access_key = os.getenv("AWS_ACCESS_SECRET")
        if not aws_access_key or not aws_secret_access_key:
            config = Config(
                signature_version=UNSIGNED,
                retries={"max_attempts": 10, "mode": "standard"},
                connect_timeout=5,
                read_timeout=60,
            )
            s3_client = boto3.client(
                "s3",
                config=config,
            )
        else:
            config = Config(
                retries={"max_attempts": 10, "mode": "standard"},
                connect_timeout=5,
                read_timeout=60,
            )
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_access_key,
                config=config,
            )
        return s3_client

    def list_s3_files(self, filename):
        bucket_name, prefix = filename.replace("s3://", "").split("/", 1)
        paginator = self.s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
        file_keys = []
        for page in pages:
            if "Contents" in page:
                for obj in page["Contents"]:
                    file_keys.append(f"s3://{bucket_name}/{obj['Key']}")
        return file_keys

    def create_bucket_if_not_exists(self, bucket_name):
        import boto3
        from botocore.exceptions import ClientError

        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            print(f"Bucket {bucket_name} already exists.")
        except ClientError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                try:
                    self.s3_client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={
                            "LocationConstraint": (
                                boto3.session.Session().region_name
                                if boto3.session.Session().region_name
                                else "us-east-1"
                            )
                        },
                    )
                    print(f"Bucket {bucket_name} created successfully.")
                except ClientError as e:
                    if e.response["Error"]["Code"] == "BucketAlreadyExists":
                        print(f"Bucket {bucket_name} already exists globally.")
                    elif e.response["Error"]["Code"] == "AccessDenied":
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Access denied to create bucket {bucket_name}. Error: {str(e)}",
                        )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to create bucket {bucket_name}. Error: {str(e)}",
                        )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error checking bucket {bucket_name}. Error: {str(e)}",
                )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to access bucket {bucket_name}. Error: {str(e)}",
            )

    def upload_file_to_s3(self, file_path, bucket_name, object_name):
        try:
            self.s3_client.upload_file(file_path, bucket_name, object_name)
            print(f"Uploaded {file_path} to {bucket_name}/{object_name}.")
        except Exception as e:
            print(f"Failed to upload {file_path}. Error: {str(e)}")

    def upload_folder_to_s3(self, bucket_name, local_dir):
        base_dir_name = "model_and_data"

        for root, _, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, local_dir)
                s3_path = os.path.join(base_dir_name, relative_path)

                try:
                    self.s3_client.upload_file(local_path, bucket_name, s3_path)
                    print(f"Uploaded {local_path} to {bucket_name}/{s3_path}.")
                except Exception as e:
                    print(f"Failed to upload {local_path}. Error: {str(e)}")
