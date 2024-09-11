import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Protocol, Set, Tuple

from fastapi import Response, UploadFile
from thirdai import neural_db as ndb
from thirdai import neural_db_v2 as ndbv2
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


def convert_args(args: Dict[str, Any], rename: Dict[str, str], remove: Set[str]):
    return {rename.get(k, k): v for k, v in args.items() if k not in remove}


def convert_to_ndbv2_doc(
    resource_path: str, display_path: str, doc_args: Dict[str, Any]
) -> ndbv2.Document:
    filename, ext = os.path.splitext(resource_path)

    # TODO(V2 Support): add support for unstructured (pptx, eml, txt), and InMemoryText
    if ext == ".pdf":
        doc_args = convert_args(
            doc_args,
            rename={"metadata": "doc_metadata"},
            remove={"version", "on_disk", "save_extra_info"},
        )
        return ndbv2.PDF(resource_path, display_path=display_path, **doc_args)
    elif ext == ".docx":
        doc_args = convert_args(
            doc_args,
            rename={"metadata": "doc_metadata"},
            remove={"on_disk"},
        )
        return ndbv2.DOCX(resource_path, display_path=display_path, **doc_args)
    elif ext == ".html":
        with open(resource_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        dummy_response = Response()
        dummy_response.status_code = 200
        dummy_response._content = html_content.encode("utf-8")

        doc_args = convert_args(
            doc_args,
            rename={"metadata": "doc_metadata"},
            remove={"on_disk", "save_extra_info"},
        )
        return ndbv2.URL(
            os.path.basename(filename), response=dummy_response, **doc_args
        )
    elif ext == ".csv":
        doc_args = convert_args(
            doc_args,
            rename={
                "metadata": "doc_metadata",
                "weak_columns": "text_columns",
                "strong_columns": "keyword_columns",
            },
            remove={
                "id_column",
                "reference_columns",
                "on_disk",
                "save_extra_info",
                "has_offset",
                "use_dask",
                "blocksize",
            },
        )
        return ndbv2.CSV(resource_path, display_path=display_path, **doc_args)
    else:
        raise TypeError(f"{ext} Document type isn't supported yet.")


def preload_chunks(
    resource_path: str, display_path: str, doc_args: Dict[str, Any]
) -> Tuple[ndbv2.Document, str]:
    # TODO(V2 Support): Add an option for users to set the doc_id
    doc = convert_to_ndbv2_doc(
        resource_path=resource_path, display_path=display_path, doc_args=doc_args
    )
    return ndbv2.documents.PrebatchedDoc(doc.chunks(), doc_id=doc.doc_id())


def process_file(
    file: str, doc_save_dir: str, tmp_dir: str, doc_args: Dict[str, Any]
) -> Tuple[ndbv2.Document, str]:
    """
    Process a file, downloading it from S3 if necessary, and convert it to an NDB file.
    """
    if file.startswith("s3://"):
        s3_client = S3FileHandler().create_s3_client()
        bucket_name, prefix = file.replace("s3://", "").split("/", 1)
        local_file_path = os.path.join(tmp_dir, os.path.basename(prefix))

        # Download the file from S3
        try:
            s3_client.download_file(bucket_name, prefix, local_file_path)
        except Exception as error:
            print(f"There was an error downloading the file from s3 : {error}. {file}")
            return f"There was an error downloading the file from s3 : {error}"

        doc = preload_chunks(
            resource_path=local_file_path,
            display_path=f"/{bucket_name}.s3.amazonaws.com/{prefix}",
            doc_args=doc_args,
        )
        os.remove(local_file_path)

        return doc

    save_artifact_uuid = str(uuid.uuid4())
    doc_dir = os.path.join(doc_save_dir, save_artifact_uuid)
    os.makedirs(doc_dir, exist_ok=True)
    shutil.copy(src=file, dst=doc_dir)

    return preload_chunks(
        resource_path=os.path.join(doc_dir, os.path.basename(file)),
        display_path=os.path.join(save_artifact_uuid, os.path.basename(file)),
        doc_args=doc_args,
    )


def create_ndbv2_docs(
    documents: List[Dict[str, Any]], doc_save_dir: str, data_dir: str
) -> List[ndb.Document]:
    """
    Creates NDB documents from the provided document dictionaries.

    Args:
        documents (List[Dict[str, Any]]): List of document dictionaries.
        data_dir (str): Directory to save the files.

    Returns:
        List[ndb.Document]: List of NDBv2 documents.
    """
    ndb_docs = []

    for doc in documents:
        if doc["location"] == "local":
            doc_path = os.path.join(data_dir, os.path.basename(doc["path"]))
        else:
            doc_path = doc["path"]

        ndb_doc = process_file(
            doc_path,
            doc_save_dir=doc_save_dir,
            tmp_dir=data_dir,
            doc_args={
                k: v
                for k, v in doc.items()
                if k not in {"location", "document_type", "path"}
            },
        )

        ndb_docs.append(ndb_doc)

    return ndb_docs
