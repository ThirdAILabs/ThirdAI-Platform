import json
import os
from abc import ABC, abstractmethod
from typing import List

import boto3
from fastapi import HTTPException, UploadFile, status
from backend.config import FileInfo, FileLocation


def model_bazaar_path():
    return (
        "/model_bazaar"
        if os.path.exists("/.dockerenv")
        else os.getenv("SHARE_DIR", "/model_bazaar")
    )


def download_files(
    files: List[UploadFile], file_infos: List[FileInfo], dest_dir: str
) -> List[FileInfo]:
    filename_to_file = {file.filename: file for file in files}

    os.makedirs(dest_dir, exist_ok=True)

    all_files = []
    for file_info in file_infos:
        handler = StorageHandlerFactory.get_handler(file_info.location)()

        file = filename_to_file.get(os.path.basename(file_info.path), None)
        try:
            filenames = handler.process_files(file_info, file, dest_dir)
        except Exception as error:
            raise ValueError(
                f"Error processing file '{file_info.path}' from '{file_info.location}': {error}"
            )

        all_files.extend(
            FileInfo(
                path=filename,
                location=file_info.location,
                doc_id=file_info.doc_id if len(filenames) == 1 else None,
                options=file_info.options,
                metadata=file_info.metadata,
            )
            for filename in filenames
        )

    return all_files


class StorageHandler(ABC):
    """
    Abstract base class for storage handlers.

    Methods:
    - process_files: Abstract method to process files.
    - validate_file: Abstract method to validate files.
    """

    @abstractmethod
    def process_files(
        self, file_info: FileInfo, file: UploadFile, destination_dir: str
    ):
        pass


class LocalStorageHandler(StorageHandler):
    """
    Local storage handler for processing and validating local files.

    Methods:
    - process_files: Processes and saves the local file.
    - validate_file: Validates the local file.
    """

    def process_files(
        self, file_info: FileInfo, file: UploadFile, destination_dir: str
    ):
        destination_path = os.path.join(destination_dir, file.filename)
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        with open(destination_path, "wb") as f:
            f.write(file.file.read())
        file.file.close()
        return [destination_path]


class NFSStorageHandler(StorageHandler):
    """
    NFS storage handler for processing and validating NFS files.

    Methods:
    - process_files: Processes and saves the NFS file.
    - validate_file: Validates the NFS file.
    """

    def process_files(
        self, file_info: FileInfo, file: UploadFile, destination_dir: str
    ):
        if os.path.isdir(file_info.path):
            filenames = []
            for root, _, files_in_dir in os.walk(file_info.path):
                filenames.extend(
                    os.path.join(root, filename) for filename in files_in_dir
                )
            return filenames
        else:
            return [file_info.path]


class S3StorageHandler(StorageHandler):
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

    def process_files(
        self, file_info: FileInfo, file: UploadFile, destination_dir: str
    ):
        return self.list_s3_files(file_info.path)

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


class StorageHandlerFactory:
    """
    Factory class to get the correct storage handler based on location.

    Attributes:
    - handlers: Dictionary mapping FileLocation to handler classes.

    Methods:
    - get_handler: Returns the handler class for the specified location.
    """

    handlers = {
        FileLocation.local: LocalStorageHandler,
        FileLocation.nfs: NFSStorageHandler,
        FileLocation.s3: S3StorageHandler,
    }

    @classmethod
    def get_handler(cls, location):
        handler_class = cls.handlers.get(location)
        if not handler_class:
            raise ValueError(f"No handler found for location: {location}")
        return handler_class
