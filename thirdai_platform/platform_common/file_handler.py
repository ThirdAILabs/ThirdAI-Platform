import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from functools import wraps
from typing import List

import boto3
from botocore import UNSIGNED
from botocore.client import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile, status
from platform_common.pydantic_models.training import FileInfo, FileLocation


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


def expand_cloud_buckets_and_directories(file_infos: List[FileInfo]) -> List[FileInfo]:
    """
    This function takes in a list of file infos and expands it so that each file info
    represents a single file that can be passed to NDB or UDT. This is because we allow
    users to specify s3, gcp, azure buckets or nfs directories in train, that could contain multiple
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
            s3_client = get_cloud_client(provider="s3")
            bucket_name, source_path = file_info.parse_s3_url()
            s3_objects = s3_client.list_files(
                bucket_name=bucket_name, source_path=source_path
            )
            expanded_files.extend(
                expand_file_info(paths=s3_objects, file_info=file_info)
            )
        elif file_info.location == FileLocation.azure:
            azure_client = get_cloud_client(provider="azure")
            container_name, blob_path = file_info.parse_azure_url()
            azure_objects = azure_client.list_files(
                bucket_name=container_name, source_path=blob_path
            )
            expanded_files.extend(
                expand_file_info(
                    paths=[
                        azure_client.full_path(
                            bucket_name=container_name, source_path=azure_object
                        )
                        for azure_object in azure_objects
                    ],
                    file_info=file_info,
                )
            )
        elif file_info.location == FileLocation.gcp:
            gcp_client = get_cloud_client(provider="gcp")
            bucket_name, source_path = file_info.parse_gcp_url()
            gcp_objects = gcp_client.list_files(bucket_name, source_path)
            expanded_files.extend(
                expand_file_info(
                    paths=[
                        gcp_client.full_path(
                            bucket_name=bucket_name, source_path=gcp_object
                        )
                        for gcp_object in gcp_objects
                    ],
                    file_info=file_info,
                )
            )
        elif file_info.location == FileLocation.nfs:
            directory_files = list_files_in_nfs_dir(file_info.path)
            expanded_files.extend(
                expand_file_info(paths=directory_files, file_info=file_info)
            )
    return expanded_files


def handle_exceptions(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            class_name = args[0].__class__.__name__ if args else "UnknownClass"
            method_name = func.__name__
            logging.error(
                f"Error in class '{class_name}', method '{method_name}' "
                f"with arguments {args[1:]}, and keyword arguments {kwargs}. "
                f"Error: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {str(e)}",
            )

    return wrapper


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

    @abstractmethod
    def generate_url_from_source(self, source: str, expiry_mins: int = 15):
        pass


class S3StorageHandler(CloudStorageHandler):
    """
    S3 storage handler implementation.
    """

    def __init__(
        self, aws_access_key=None, aws_secret_access_key=None, region_name=None
    ):
        self.s3_client = self.create_s3_client(
            aws_access_key=aws_access_key,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )

    @handle_exceptions
    def create_s3_client(
        self, aws_access_key=None, aws_secret_access_key=None, region_name=None
    ):
        # TODO(YASH): Customers will also have rotating aws session token so add that support.
        # https://docs.aws.amazon.com/sdk-for-php/v3/developer-guide/guide_credentials_environment.html
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
                signature_version="s3v4",
            )
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_access_key,
                config=config,
                region_name=region_name,
            )
        return s3_client

    @handle_exceptions
    def create_bucket_if_not_exists(self, bucket_name: str):
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            logging.warning(f"Bucket {bucket_name} already exists.")
        except ClientError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                try:
                    self.s3_client.create_bucket(
                        Bucket=bucket_name,
                    )
                    logging.info(f"Bucket {bucket_name} created successfully.")
                except ClientError as e:
                    if e.response["Error"]["Code"] == "BucketAlreadyExists":
                        logging.warning(
                            f"Bucket {bucket_name} already exists globally."
                        )
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

    @handle_exceptions
    def generate_signed_url(
        self, bucket_name: str, source_path: str, expiry_mins: int = 15
    ):
        try:
            response = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket_name, "Key": source_path},
                ExpiresIn=expiry_mins * 60,
            )
        except ClientError as e:
            logging.error(f"Failed to generate presigned URL: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate presigned URL: {str(e)}",
            )
        return response

    @handle_exceptions
    def generate_url_from_source(self, source: str, expiry_mins: int = 15):
        """
        Parse the path stored in the format '/{bucket_name}.s3.amazonaws.com/{prefix}'
        to get the bucket name and the object key for downloading.
        """
        # Remove leading slash and split on '.s3.amazonaws.com/'
        if source.startswith("/"):
            source = source[1:]
        parts = source.split(".s3.amazonaws.com/", 1)

        if len(parts) != 2:
            raise ValueError(f"Invalid S3 source: {source}")

        bucket_name = parts[0]  # bucket_name
        object_key = parts[1]  # object_key (prefix)
        return self.generate_signed_url(
            bucket_name=bucket_name, source_path=object_key, expiry_mins=expiry_mins
        )


class AzureStorageHandler(CloudStorageHandler):
    def __init__(self, account_name=None, account_key=None):
        self._blob_service_client = self.create_azure_client(
            account_name=account_name, account_key=account_key
        )
        self._account_name = account_name

    @handle_exceptions
    def create_azure_client(self, account_name=None, account_key=None):
        from azure.storage.blob import BlobServiceClient

        if account_name and account_key:
            # Authenticated access
            connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
            blob_service_client = BlobServiceClient.from_connection_string(
                conn_str=connection_string
            )
        elif account_name:
            # Anonymous (public) access using account_url
            account_url = f"https://{account_name}.blob.core.windows.net"
            blob_service_client = BlobServiceClient(account_url=account_url)
        else:
            raise ValueError("Account name is required for Azure Blob Storage.")

        return blob_service_client

    @handle_exceptions
    def container_client(self, bucket_name: str):
        return self._blob_service_client.get_container_client(container=bucket_name)

    @handle_exceptions
    def full_path(self, bucket_name: str, source_path: str):
        return f"https://{self._account_name}.blob.core.windows.net/{bucket_name}/{source_path}"

    @handle_exceptions
    def create_bucket_if_not_exists(self, bucket_name: str):
        container_client = self.container_client(bucket_name=bucket_name)
        if not container_client.exists():
            container_client.create_container()
            logging.info(f"Container {bucket_name} created successfully.")
        else:
            logging.warning(f"Container {bucket_name} already exists.")

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

    @handle_exceptions
    def generate_signed_url(
        self, bucket_name: str, source_path: str, expiry_mins: int = 15
    ):
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas

        # Check if the blob is public
        if (
            self._blob_service_client.credential is None
        ):  # Public access (no credentials)
            return self.full_path(bucket_name, source_path)

        container_client = self.container_client(bucket_name=bucket_name)
        blob_client = container_client.get_blob_client(blob=source_path)

        sas_token = generate_blob_sas(
            account_name=self._account_name,
            container_name=bucket_name,
            blob_name=source_path,
            account_key=self._blob_service_client.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(minutes=expiry_mins),
        )

        return f"{blob_client.url}?{sas_token}"

    @handle_exceptions
    def generate_url_from_source(self, source: str, expiry_mins: int = 15):
        """
        Parse the display path stored in the format '/{account_name}.blob.core.windows.net/{container_name}/{blob_name}'
        to get the container name and blob name for downloading.
        """
        # Remove leading slash and split on '.blob.core.windows.net/'
        if source.startswith("/"):
            source = source[1:]
        parts = source.split(".blob.core.windows.net/", 1)

        if len(parts) != 2:
            raise ValueError(f"Invalid Azure Blob display path: {source}")

        container_name, blob_name = parts[1].split("/", 1)
        return self.generate_signed_url(
            bucket_name=container_name, source_path=blob_name, expiry_mins=expiry_mins
        )


class GCPStorageHandler(CloudStorageHandler):
    def __init__(self, credentials_file_path: str = None):
        from google.cloud import storage

        if credentials_file_path:
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
        else:
            self._client = storage.Client.create_anonymous_client()

    @handle_exceptions
    def create_bucket_if_not_exists(self, bucket_name: str):
        bucket = self._client.lookup_bucket(bucket_name)
        if bucket:
            logging.info(f"Bucket {bucket_name} already exists.")
        else:
            self._client.create_bucket(bucket_name)
            logging.warning(f"Bucket {bucket_name} created successfully.")

    @handle_exceptions
    def full_path(self, bucket_name: str, source_path: str):
        return f"gs://{bucket_name}/{source_path}"

    @handle_exceptions
    def full_web_path(self, bucket_name: str, source_path: str):
        return f"https://storage.googleapis.com/{bucket_name}/{source_path}"

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
        # Filter out any blobs that end with a `/`, which represents folders
        blob_names = [blob.name for blob in blobs if not blob.name.endswith("/")]
        return blob_names

    @handle_exceptions
    def delete_bucket(self, bucket_name: str):
        bucket = self._client.bucket(bucket_name)

        blobs = list(bucket.list_blobs())
        for blob in blobs:
            blob.delete()

        bucket.delete()

    @handle_exceptions
    def delete_path(self, bucket_name: str, source_path: str):
        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(source_path)
        blob.delete()

    @handle_exceptions
    def generate_signed_url(
        self, bucket_name: str, source_path: str, expiry_mins: int = 15
    ):
        from google.auth.credentials import AnonymousCredentials

        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(source_path)

        # Check if the credentials are anonymous (public bucket)
        if isinstance(self._client._credentials, AnonymousCredentials):
            # Return the direct URL for public access
            return self.full_web_path(bucket_name, source_path)

        try:
            url = blob.generate_signed_url(
                expiration=timedelta(minutes=expiry_mins),
                method="GET",
            )
        except Exception as e:
            logging.error(f"Failed to generate signed URL: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate signed URL: {str(e)}",
            )

        return url

    @handle_exceptions
    def generate_url_from_source(self, source: str, expiry_mins: int = 15):
        """
        Parse the display path stored in the format '/storage.googleapis.com/{bucket_name}/{blob_name}'
        to get the bucket name and blob name for downloading.
        """
        # Remove leading slash and split on 'storage.googleapis.com/'
        if source.startswith("/"):
            source = source[1:]
        parts = source.split("storage.googleapis.com/", 1)

        if len(parts) != 2:
            raise ValueError(f"Invalid GCP display path: {source}")

        bucket_name, blob_name = parts[1].split("/", 1)
        return self.generate_signed_url(
            bucket_name=bucket_name, source_path=blob_name, expiry_mins=expiry_mins
        )


# TODO( YASH): Configure these variables through api endpoints, so that users can change through course of time.
def get_cloud_client(provider: str):
    if provider == "s3":
        aws_access_key = os.getenv("AWS_ACCESS_KEY", None)
        aws_secret_access_key = os.getenv("AWS_ACCESS_SECRET", None)
        region_name = os.getenv("AWS_REGION_NAME", None) or None
        return S3StorageHandler(
            aws_access_key=aws_access_key,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )
    elif provider == "azure":
        account_name = os.getenv("AZURE_ACCOUNT_NAME", None)
        account_key = os.getenv("AZURE_ACCOUNT_KEY", None)
        return AzureStorageHandler(account_name=account_name, account_key=account_key)
    elif provider == "gcp":
        gcp_credentials_file = os.getenv("GCP_CREDENTIALS_FILE", None)
        return GCPStorageHandler(credentials_file_path=gcp_credentials_file)
    else:
        raise ValueError(
            f"Currently supports s3,azure and gcp, but received {provider}"
        )


def download_file(doc: FileInfo, tmp_dir: str):
    """
    General method to download a file from S3, Azure, or GCP to a temporary directory.
    """
    local_file_path = None

    if doc.location == FileLocation.s3:
        s3_client = get_cloud_client(provider="s3")
        bucket_name, prefix = doc.parse_s3_url()
        local_file_path = os.path.join(tmp_dir, os.path.basename(prefix))

        try:
            s3_client.download_file(bucket_name, prefix, local_file_path)
        except Exception as error:
            logging.error(
                f"There was an error downloading the file from S3: {error}. {doc.path}"
            )
            return None

    elif doc.location == FileLocation.azure:
        azure_client = get_cloud_client(provider="azure")
        container_name, blob_name = doc.parse_azure_url()
        local_file_path = os.path.join(tmp_dir, os.path.basename(blob_name))

        try:
            azure_client.download_file(container_name, blob_name, local_file_path)
        except Exception as error:
            logging.error(
                f"There was an error downloading the file from Azure: {error}. {doc.path}"
            )
            return None

    elif doc.location == FileLocation.gcp:
        gcp_client = get_cloud_client(provider="gcp")
        bucket_name, blob_name = doc.parse_gcp_url()
        local_file_path = os.path.join(tmp_dir, os.path.basename(blob_name))

        try:
            gcp_client.download_file(bucket_name, blob_name, local_file_path)
        except Exception as error:
            logging.error(
                f"There was an error downloading the file from GCP: {error}. {doc.path}"
            )
            return None

    return local_file_path


def get_local_file_infos(files: List[FileInfo], tmp_dir: str):
    local_file_infos = []
    for file in files:
        if file.location in {FileLocation.s3, FileLocation.azure, FileLocation.gcp}:
            # Download the cloud file to the temporary directory
            local_file_path = download_file(file, tmp_dir)
            if local_file_path:
                local_file_infos.append(
                    FileInfo(
                        path=local_file_path,
                        metadata=file.metadata,
                        options=file.options,
                        location=FileLocation.local,
                    )
                )
            else:
                logging.error(f"Failed to download cloud file: {file.path}")
        else:
            # Local files can be used as-is
            local_file_infos.append(file)

    return local_file_infos
