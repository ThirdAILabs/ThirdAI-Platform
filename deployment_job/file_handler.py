import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Protocol

from fastapi import UploadFile, status
from thirdai import neural_db as ndb
from utils import FILE_DOCUMENT_TYPES


# Protocol for FileHandler
class FileHandler(Protocol):
    def handle(self, doc: Dict[str, Any], data_dir: str) -> str:
        """
        Handles the file operation and returns the modified file path.

        Args:
            doc (Dict[str, Any]): Document dictionary.
            data_dir (str): Directory to save the files.

        Returns:
            str: Path to the processed file.
        """
        ...

    def finish(self, doc: Dict[str, Any], ndb_doc: Any, data_dir: str) -> Any:
        """
        Finalizes the file operation and returns the modified ndb_doc.

        Args:
            doc (Dict[str, Any]): Document dictionary.
            ndb_doc (Any): The NDB document object to finalize.
            data_dir (str): Directory to save the files.

        Returns:
            Any: The modified NDB document.
        """
        ...


# Local file handler
class LocalFileHandler:
    def handle(self, doc: Dict[str, Any], data_dir: str) -> str:
        try:
            file_path = os.path.join(data_dir, os.path.basename(doc["path"]))
            if not os.path.exists(file_path):
                raise Exception(f"File {file_path} does not exist.")
            return file_path
        except Exception as error:
            raise Exception(f"There was an error handling the file from local: {error}")

    def finish(self, doc: Dict[str, Any], ndb_doc: Any, data_dir: str) -> Any:
        # No finalization needed for local files
        return ndb_doc


# NFS file handler
class NFSFileHandler:
    def handle(self, doc: Dict[str, Any], data_dir: str) -> str:
        try:
            file_path = os.path.join(data_dir, os.path.basename(doc["path"]))
            shutil.copy(doc["path"], file_path)
            return file_path
        except Exception as error:
            raise Exception(f"There was an error reading the file from NFS: {error}")

    def finish(self, doc: Dict[str, Any], ndb_doc: Any, data_dir: str) -> Any:
        # No finalization needed for NFS files
        return ndb_doc


# S3 file handler
class S3FileHandler:
    def __init__(self):
        self.s3_client = self.create_s3_client()

    def create_s3_client(self):
        import boto3
        from botocore import UNSIGNED
        from botocore.client import Config

        aws_access_key = os.getenv("AWS_ACCESS_KEY")
        aws_secret_access_key = os.getenv("AWS_ACCESS_SECRET")
        if not aws_access_key or not aws_secret_access_key:
            config = Config(
                retries={"max_attempts": 10, "mode": "standard"},
                connect_timeout=5,
                read_timeout=60,
                signature_version=UNSIGNED,
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

    def handle(self, doc: Dict[str, Any], data_dir: str) -> str:
        bucket, object = doc["path"].replace("s3://", "").split("/", 1)
        try:
            file_path = os.path.join(data_dir, os.path.basename(doc["path"]))
            self.s3_client.download_file(bucket, object, file_path)
            return file_path
        except Exception as error:
            raise Exception(f"There was an error downloading the file from S3: {error}")

    def finish(self, doc: Dict[str, Any], ndb_doc: Any, data_dir: str) -> Any:
        bucket, object = doc["path"].replace("s3://", "").split("/", 1)
        ndb_doc.path = Path(f"/{bucket}.s3.amazonaws.com/{object}")
        file_path = os.path.join(data_dir, os.path.basename(doc["path"]))
        if os.path.exists(file_path):
            os.remove(file_path)
        return ndb_doc

    def download_file(self, s3_url: str, file_path: str):
        bucket, object = s3_url.replace("s3://", "").split("/", 1)
        try:
            self.s3_client.download_file(bucket, object, file_path)
        except Exception as error:
            raise Exception(f"There was an error downloading the file from S3: {error}")


def validate_files(
    documents: List[Dict[str, Any]], files: List[UploadFile], data_dir: str
) -> None:
    """
    Validates that all required files are provided for the documents and saves them to the data directory.

    Args:
        documents (List[Dict[str, Any]]): List of document dictionaries.
        files (List[UploadFile]): List of uploaded files.
        data_dir (str): Directory to save the files.

    Raises:
        Exception: If there is a mismatch between documents and uploaded files or an error during file handling.
    """
    filename_to_file = {file.filename: file for file in files}

    filenames = set(filename_to_file.keys())
    file_doc_names = set(
        [
            os.path.basename(doc["path"])
            for doc in documents
            if doc["location"] == "local"
            and doc["document_type"] in FILE_DOCUMENT_TYPES
        ]
    )
    if filenames != file_doc_names:
        raise Exception("Mismatch between documents and uploaded files")

    for file in files:
        file_path = os.path.join(data_dir, file.filename)
        with open(file_path, "wb") as f:
            f.write(file.file.read())


def create_ndb_docs(
    documents: List[Dict[str, Any]], data_dir: str
) -> List[ndb.Document]:
    """
    Creates NDB documents from the provided document dictionaries.

    Args:
        documents (List[Dict[str, Any]]): List of document dictionaries.
        data_dir (str): Directory to save the files.

    Returns:
        List[ndb.Document]: List of NDB documents.
    """
    handlers = {
        "local": LocalFileHandler(),
        "nfs": NFSFileHandler(),
        "s3": S3FileHandler(),
    }

    ndb_docs = []

    for doc in documents:
        handler = handlers.get(doc["location"])
        if handler:
            file_path = handler.handle(doc, data_dir)
        else:
            raise Exception(f"Unsupported location: {doc['location']}")

        if doc["document_type"] in FILE_DOCUMENT_TYPES:
            ndb_doc_params = {
                key: value
                for key, value in doc.items()
                if key not in {"document_type", "location", "path"}
            }
            ndb_doc = getattr(ndb, doc["document_type"])(file_path, **ndb_doc_params)
        else:
            ndb_doc_params = {
                key: value
                for key, value in doc.items()
                if key not in {"document_type", "location"}
            }
            ndb_doc = getattr(ndb, doc["document_type"])(**ndb_doc_params)

        ndb_doc = handler.finish(doc, ndb_doc, data_dir)
        ndb_docs.append(ndb_doc)

    return ndb_docs
