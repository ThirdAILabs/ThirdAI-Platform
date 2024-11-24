import logging
import os
import shutil
import uuid
from typing import Any, Dict, Optional, Tuple

import pdftitle
from fastapi import Response
from platform_common.file_handler import FileInfo, FileLocation, download_file
from thirdai import neural_db_v2 as ndbv2


def convert_to_ndb_doc(
    resource_path: str,
    display_path: str,
    doc_id: Optional[str],
    metadata: Optional[Dict[str, Any]],
    options: Dict[str, Any],
) -> Optional[ndbv2.Document]:
    filename, ext = os.path.splitext(resource_path)
    ext = ext.lower()
    if ext == ".pdf":
        doc_keywords = ""
        if options.get("title_as_keywords", False):
            try:
                pdf_title = pdftitle.get_title_from_file(resource_path)
                filename_as_keywords = (
                    resource_path.strip(".pdf").replace("-", " ").replace("_", " ")
                )
                keyword_weight = options.get("keyword_weight", 10)
                doc_keywords = (
                    (pdf_title + " " + filename_as_keywords + " ") * keyword_weight,
                )
            except Exception as e:
                logging.error(
                    f"Could not parse pdftitle for pdf: {resource_path}. Error: {e}"
                )

        return ndbv2.PDF(
            resource_path,
            doc_metadata=metadata,
            display_path=display_path,
            doc_id=doc_id,
            doc_keywords=doc_keywords,
        )
    elif ext == ".docx":
        return ndbv2.DOCX(
            resource_path,
            doc_metadata=metadata,
            display_path=display_path,
            doc_id=doc_id,
        )
    elif ext == ".html":
        with open(resource_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        dummy_response = Response()
        dummy_response.status_code = 200
        dummy_response._content = html_content.encode("utf-8")

        return ndbv2.URL(
            os.path.basename(filename),
            response=dummy_response,
            doc_metadata=metadata,
            doc_id=doc_id,
        )
    elif ext == ".csv":
        return ndbv2.CSV(
            resource_path,
            keyword_columns=options.get("csv_strong_columns", []),
            text_columns=options.get("csv_weak_columns", []),
            metadata_columns=options.get("csv_metadata_columns", []),
            doc_metadata=metadata,
            display_path=display_path,
            doc_id=doc_id,
        )
    else:
        logging.warning("{ext} Document type isn't supported yet.")
        return None


def preload_chunks(
    resource_path: str,
    display_path: str,
    doc_id: Optional[str],
    metadata: Optional[Dict[str, Any]],
    options: Dict[str, Any],
) -> Optional[Tuple[ndbv2.Document, str]]:
    doc = convert_to_ndb_doc(
        resource_path=resource_path,
        display_path=display_path,
        doc_id=doc_id,
        metadata=metadata,
        options=options,
    )
    if not doc:
        return None
    return ndbv2.documents.PrebatchedDoc(list(doc.chunks()), doc_id=doc.doc_id())


def parse_doc(
    doc: FileInfo, doc_save_dir: str, tmp_dir: str
) -> Optional[Tuple[ndbv2.Document, str]]:
    """
    Process a file, downloading it from S3, Azure, or GCP if necessary,
    and convert it to an NDB file.
    """
    if doc.location in {FileLocation.s3, FileLocation.azure, FileLocation.gcp}:
        local_file_path = download_file(doc, tmp_dir)
        if not local_file_path:
            raise ValueError(f"Error downloading file '{doc.path}' from {doc.location}")

        # Set display_path based on the cloud provider
        if doc.location == FileLocation.s3:
            bucket_name, prefix = doc.parse_s3_url()
            display_path = f"/{bucket_name}.s3.amazonaws.com/{prefix}"
        elif doc.location == FileLocation.azure:
            account_name = os.getenv("AZURE_ACCOUNT_NAME")
            container_name, blob_name = doc.parse_azure_url()
            display_path = (
                f"/{account_name}.blob.core.windows.net/{container_name}/{blob_name}"
            )
        elif doc.location == FileLocation.gcp:
            bucket_name, blob_name = doc.parse_gcp_url()
            display_path = f"/storage.googleapis.com/{bucket_name}/{blob_name}"
    else:
        # Local file handling
        save_artifact_uuid = str(uuid.uuid4())
        artifact_dir = os.path.join(doc_save_dir, save_artifact_uuid)
        os.makedirs(artifact_dir, exist_ok=True)
        local_file_path = os.path.join(artifact_dir, os.path.basename(doc.path))
        shutil.copy(src=doc.path, dst=artifact_dir)
        display_path = os.path.join(save_artifact_uuid, os.path.basename(doc.path))

    # Convert the downloaded or local file into an NDB document
    ndb_doc = preload_chunks(
        resource_path=local_file_path,
        display_path=display_path,
        doc_id=doc.doc_id,
        metadata=doc.metadata,
        options=doc.options,
    )

    # Remove the local file if it was downloaded from cloud storage
    if doc.location in {FileLocation.s3, FileLocation.azure, FileLocation.gcp}:
        os.remove(local_file_path)

    return ndb_doc
