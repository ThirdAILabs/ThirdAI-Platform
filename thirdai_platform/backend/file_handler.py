import os
from abc import ABC, abstractmethod
from typing import List

from backend.train_config import FileInfo, FileLocation
from backend.utils import handle_exceptions
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


class CloudStorageHandler(ABC):
    """
    Interface for Cloud Storage Handlers.
    All cloud storage handlers must implement these methods.
    """

    @abstractmethod
    def create_bucket_if_not_exists(self, bucket_name: str):
        pass

    @abstractmethod
    def upload_file(self, source_path: str, bucket_name: str, dest_path: str):
        pass

    @abstractmethod
    def upload_folder(self, bucket_name: str, source_dir: str, dest_dir: str):
        pass

    @abstractmethod
    def download_file(self, bucket_name: str, source_path: str, dest_path: str):
        pass

    @abstractmethod
    def download_folder(self, bucket_name: str, source_dir: str, dest_dir: str):
        pass

    @abstractmethod
    def list_files(self, bucket_name: str, source_path: str):
        pass

    @abstractmethod
    def delete_bucket(self, bucket_name: str):
        pass

    @abstractmethod
    def delete_path(self, bucket_name: str, source_path: str):
        pass


class S3StorageHandler(CloudStorageHandler):
    """
    S3 storage handler implementation.
    """

    def __init__(self, aws_access_key=None, aws_secret_access_key=None):
        self.s3_client = self.create_s3_client(
            aws_access_key=aws_access_key, aws_secret_access_key=aws_secret_access_key
        )

    @handle_exceptions
    def create_s3_client(self, aws_access_key=None, aws_secret_access_key=None):
        import boto3
        from botocore import UNSIGNED
        from botocore.client import Config

        if not aws_access_key or not aws_secret_access_key:
            config = Config(
                signature_version=UNSIGNED,
                retries={"max_attempts": 10, "mode": "standard"},
                connect_timeout=5,
                read_timeout=60,
            )
            s3_client = boto3.client("s3", config=config)
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

    @handle_exceptions
    def create_bucket_if_not_exists(self, bucket_name: str):
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

    @handle_exceptions
    def upload_file(self, source_path: str, bucket_name: str, dest_path: str):
        self.s3_client.upload_file(source_path, bucket_name, dest_path)

    @handle_exceptions
    def upload_folder(self, bucket_name: str, source_dir: str, dest_dir: str):
        for root, _, files in os.walk(source_dir):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, source_dir)
                s3_path = os.path.join(dest_dir, relative_path)
                self.upload_file(local_path, bucket_name, s3_path)

    @handle_exceptions
    def download_file(self, bucket_name: str, source_path: str, dest_path: str):
        self.s3_client.download_file(bucket_name, source_path, dest_path)

    @handle_exceptions
    def download_folder(self, bucket_name: str, source_dir: str, dest_dir: str):
        s3_files = self.list_files(bucket_name=bucket_name, source_path=source_dir)

        os.makedirs(dest_dir, exist_ok=True)

        for s3_file in s3_files:
            object_key = s3_file.replace(f"s3://{bucket_name}/", "")

            # Define the relative path for the local destination
            relative_path = object_key[len(source_dir) :].lstrip("/")
            dest_path = os.path.join(dest_dir, relative_path)

            # Ensure the directory structure exists locally
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            self.download_file(bucket_name, object_key, dest_path)

    @handle_exceptions
    def list_files(self, bucket_name: str, source_path: str):
        paginator = self.s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket_name, Prefix=source_path)
        file_keys = [
            f"s3://{bucket_name}/{obj['Key']}"
            for page in pages
            if "Contents" in page
            for obj in page["Contents"]
            if obj["Key"][-1] != "/"
        ]
        return file_keys

    @handle_exceptions
    def delete_bucket(self, bucket_name: str):
        # List all objects in the bucket and delete them
        bucket = self.s3_client.list_objects_v2(Bucket=bucket_name)
        if "Contents" in bucket:
            for obj in bucket["Contents"]:
                self.s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])

        # Delete the bucket itself
        self.s3_client.delete_bucket(Bucket=bucket_name)

    @handle_exceptions
    def delete_path(self, bucket_name: str, source_path: str):
        if source_path.startswith(f"s3://{bucket_name}/"):
            object_key = source_path[len(f"s3://{bucket_name}/") :]
        else:
            object_key = source_path  # If it's already just the object key

        self.s3_client.delete_object(Bucket=bucket_name, Key=object_key)


class AzureStorageHandler(CloudStorageHandler):
    """
    Azure storage handler implementation.
    """

    def __init__(self, account_name, account_key):
        from azure.storage.blob import BlobServiceClient

        connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"

        self._blob_service_client = BlobServiceClient.from_connection_string(
            conn_str=connection_string
        )

    @handle_exceptions
    def container_client(self, bucket_name: str):
        return self._blob_service_client.get_container_client(container=bucket_name)

    @handle_exceptions
    def create_bucket_if_not_exists(self, bucket_name: str):
        container_client = self.container_client(bucket_name=bucket_name)
        if not container_client.exists():
            container_client.create_container()
            print(f"Container {bucket_name} created successfully.")
        else:
            print(f"Container {bucket_name} already exists.")

    @handle_exceptions
    def upload_file(self, source_path: str, bucket_name: str, dest_path: str):
        container_client = self.container_client(bucket_name=bucket_name)

        blob_client = container_client.get_blob_client(blob=dest_path)

        with open(source_path, "rb") as file:
            blob_client.upload_blob(file.read(), overwrite=True)

    @handle_exceptions
    def upload_folder(self, bucket_name: str, source_dir: str, dest_dir: str):
        container_client = self.container_client(bucket_name=bucket_name)

        for root, _, files in os.walk(source_dir):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, source_dir)
                blob_path = os.path.join(dest_dir, relative_path)

                blob_client = container_client.get_blob_client(blob=blob_path)
                with open(local_path, "rb") as data:
                    blob_client.upload_blob(data.read(), overwrite=True)

    @handle_exceptions
    def download_file(self, bucket_name: str, source_path: str, dest_path: str):
        container_client = self.container_client(bucket_name=bucket_name)

        blob_client = container_client.get_blob_client(blob=source_path)

        # This returns a StorageStreamDownloader
        stream = blob_client.download_blob()
        with open(dest_path, "wb+") as local_file:
            # Read data in chunks to avoid loading all into memory at once
            for chunk in stream.chunks():
                # Process your data (anything can be done here - 'chunk' is a byte array)
                local_file.write(chunk)

    @handle_exceptions
    def download_folder(self, bucket_name: str, source_dir: str, dest_dir: str):
        blobs = self.list_files(bucket_name, source_dir)
        for blob in blobs:
            relative_path = os.path.relpath(blob, source_dir)
            dest_path = os.path.join(dest_dir, relative_path)

            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            self.download_file(bucket_name, blob, dest_path)

    @handle_exceptions
    def list_files(self, bucket_name: str, source_path: str):
        container_client = self.container_client(bucket_name=bucket_name)
        blobs = container_client.list_blobs(name_starts_with=source_path)
        blob_names = [blob.name for blob in blobs]
        return blob_names

    @handle_exceptions
    def delete_bucket(self, bucket_name: str):
        container_client = self.container_client(bucket_name)
        container_client.delete_container()

    @handle_exceptions
    def delete_path(self, bucket_name: str, source_path: str):
        container_client = self.container_client(bucket_name=bucket_name)
        blob_client = container_client.get_blob_client(blob=source_path)

        blob_client.delete_blob()


class GCPStorageHandler(CloudStorageHandler):
    """
    GCP storage handler implementation.
    """

    def __init__(self, credentials_file_path: str):
        from google.cloud import storage
        from google.oauth2 import service_account

        try:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_file_path
            )
            self._client = storage.Client(credentials=credentials)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to authenticate using the provided service account file: {str(e)}",
            )

    @handle_exceptions
    def create_bucket_if_not_exists(self, bucket_name: str):
        bucket = self._client.lookup_bucket(bucket_name)
        if bucket:
            print(f"Bucket {bucket_name} already exists.")
        else:
            self._client.create_bucket(bucket_name)
            print(f"Bucket {bucket_name} created successfully.")

    @handle_exceptions
    def upload_file(self, source_path: str, bucket_name: str, dest_path: str):
        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(dest_path)

        with open(source_path, "rb") as file:
            blob.upload_from_file(file)

    @handle_exceptions
    def upload_folder(self, bucket_name: str, source_dir: str, dest_dir: str):
        for root, _, files in os.walk(source_dir):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, source_dir)
                cloud_path = os.path.join(dest_dir, relative_path)

                self.upload_file(local_path, bucket_name, cloud_path)

    @handle_exceptions
    def download_file(self, bucket_name: str, source_path: str, dest_path: str):
        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(source_path)

        blob.download_to_filename(dest_path)

    @handle_exceptions
    def download_folder(self, bucket_name: str, source_dir: str, dest_dir: str):
        blobs = self.list_files(bucket_name, source_dir)
        for blob_name in blobs:
            relative_path = os.path.relpath(blob_name, source_dir)
            dest_path = os.path.join(dest_dir, relative_path)

            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            self.download_file(bucket_name, blob_name, dest_path)

    @handle_exceptions
    def list_files(self, bucket_name: str, source_path: str):
        bucket = self._client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=source_path)
        blob_names = [blob.name for blob in blobs]
        return blob_names

    @handle_exceptions
    def delete_bucket(self, bucket_name: str):
        bucket = self._client.bucket(bucket_name)

        # List and delete all objects in the bucket
        blobs = list(bucket.list_blobs())
        for blob in blobs:
            blob.delete()

        # Delete the bucket
        bucket.delete()

    @handle_exceptions
    def delete_path(self, bucket_name: str, source_path: str):
        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(source_path)
        blob.delete()
