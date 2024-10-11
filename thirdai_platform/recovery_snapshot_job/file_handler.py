from abc import ABC, abstractmethod

from utils import handle_exceptions


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
    def list_files(self, bucket_name: str, source_path: str):
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
                        raise ValueError(
                            f"Access denied to create bucket {bucket_name}. Error: {str(e)}",
                        )
                    else:
                        raise ValueError(
                            f"Failed to create bucket {bucket_name}. Error: {str(e)}",
                        )
            else:
                raise ValueError(
                    f"Error checking bucket {bucket_name}. Error: {str(e)}",
                )
        except Exception as e:
            raise ValueError(
                f"Failed to access bucket {bucket_name}. Error: {str(e)}",
            )

    @handle_exceptions
    def upload_file(self, source_path: str, bucket_name: str, dest_path: str):
        self.s3_client.upload_file(source_path, bucket_name, dest_path)

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
    def list_files(self, bucket_name: str, source_path: str):
        container_client = self.container_client(bucket_name=bucket_name)
        blobs = container_client.list_blobs(name_starts_with=source_path)
        blob_names = [blob.name for blob in blobs]
        return blob_names

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
            raise ValueError(
                f"Failed to authenticate using the provided service account file: {str(e)}",
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
    def list_files(self, bucket_name: str, source_path: str):
        bucket = self._client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=source_path)
        blob_names = [blob.name for blob in blobs]
        return blob_names

    @handle_exceptions
    def delete_path(self, bucket_name: str, source_path: str):
        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(source_path)
        blob.delete()
