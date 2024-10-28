import os
import shutil
import uuid
from typing import Any, Dict, Optional, Tuple, List

import pdftitle
from fastapi import Response
from platform_common.file_handler import FileInfo, FileLocation, get_cloud_client
from thirdai import neural_db_v2 as ndbv2
import pickle


def convert_to_ndb_doc(
    resource_path: str,
    display_path: str,
    doc_id: Optional[str],
    metadata: Optional[Dict[str, Any]],
    options: Dict[str, Any],
) -> ndbv2.Document:
    filename, ext = os.path.splitext(resource_path)

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
                print(f"Could not parse pdftitle for pdf: {resource_path}. Error: {e}")

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
            doc_metadata=metadata,
            display_path=display_path,
            doc_id=doc_id,
        )
    else:
        raise TypeError(f"{ext} Document type isn't supported yet.")


def preload_chunks(
    resource_path: str,
    display_path: str,
    doc_id: Optional[str],
    metadata: Optional[Dict[str, Any]],
    options: Dict[str, Any],
) -> Tuple[ndbv2.Document, str]:
    doc = convert_to_ndb_doc(
        resource_path=resource_path,
        display_path=display_path,
        doc_id=doc_id,
        metadata=metadata,
        options=options,
    )
    return ndbv2.documents.PrebatchedDoc(list(doc.chunks()), doc_id=doc.doc_id())


def parse_doc(
    doc: FileInfo, doc_save_dir: str, tmp_dir: str
) -> Tuple[ndbv2.Document, str]:
    """
    Process a file, downloading it from S3, Azure, or GCP if necessary,
    and convert it to an NDB file.
    """
    # S3 handling
    if doc.location == FileLocation.s3:
        try:
            # TODO (YASH): calling get_cloud_client for every document will be a problem, we have to come up with a way to reuse client.
            s3_client = get_cloud_client(provider="s3")
            bucket_name, prefix = doc.parse_s3_url()
            local_file_path = os.path.join(tmp_dir, os.path.basename(prefix))

            s3_client.download_file(bucket_name, prefix, local_file_path)
        except Exception as error:
            print(f"Error downloading file '{doc.path}' from S3: {error}")
            raise ValueError(f"Error downloading file '{doc.path}' from S3: {error}")

        ndb_doc = preload_chunks(
            resource_path=local_file_path,
            display_path=f"/{bucket_name}.s3.amazonaws.com/{prefix}",
            doc_id=doc.doc_id,
            metadata=doc.metadata,
            options=doc.options,
        )

        os.remove(local_file_path)
        return ndb_doc

    # Azure handling
    elif doc.location == FileLocation.azure:
        try:
            account_name = os.getenv("AZURE_ACCOUNT_NAME")
            azure_client = get_cloud_client(provider="azure")
            container_name, blob_name = doc.parse_azure_url()
            local_file_path = os.path.join(tmp_dir, os.path.basename(blob_name))

            azure_client.download_file(container_name, blob_name, local_file_path)
        except Exception as error:
            print(f"Error downloading file '{doc.path}' from Azure: {error}")
            raise ValueError(f"Error downloading file '{doc.path}' from Azure: {error}")

        ndb_doc = preload_chunks(
            resource_path=local_file_path,
            display_path=f"/{account_name}.blob.core.windows.net/{container_name}/{blob_name}",
            doc_id=doc.doc_id,
            metadata=doc.metadata,
            options=doc.options,
        )

        os.remove(local_file_path)
        return ndb_doc

    # GCP handling
    elif doc.location == FileLocation.gcp:
        try:
            gcp_client = get_cloud_client(provider="gcp")
            bucket_name, blob_name = doc.parse_gcp_url()
            local_file_path = os.path.join(tmp_dir, os.path.basename(blob_name))

            gcp_client.download_file(bucket_name, blob_name, local_file_path)
        except Exception as error:
            print(f"Error downloading file '{doc.path}' from GCP: {error}")
            raise ValueError(f"Error downloading file '{doc.path}' from GCP: {error}")

        ndb_doc = preload_chunks(
            resource_path=local_file_path,
            display_path=f"/storage.googleapis.com/{bucket_name}/{blob_name}",
            doc_id=doc.doc_id,
            metadata=doc.metadata,
            options=doc.options,
        )

        os.remove(local_file_path)
        return ndb_doc

    # Local file handling
    save_artifact_uuid = str(uuid.uuid4())
    artifact_dir = os.path.join(doc_save_dir, save_artifact_uuid)
    os.makedirs(artifact_dir, exist_ok=True)
    shutil.copy(src=doc.path, dst=artifact_dir)

    return preload_chunks(
        resource_path=os.path.join(artifact_dir, os.path.basename(doc.path)),
        display_path=os.path.join(save_artifact_uuid, os.path.basename(doc.path)),
        doc_id=doc.doc_id,
        metadata=doc.metadata,
        options=doc.options,
    )


def parse_and_save(
    doc: FileInfo, doc_save_dir: str, tmp_dir: str, output_path: str
) -> dict:
    if doc.location == FileLocation.s3:
        try:
            # TODO (YASH): calling get_cloud_client for every document will be a problem, we have to come up with a way to reuse client.
            s3_client = get_cloud_client(provider="s3")
            bucket_name, prefix = doc.parse_s3_url()
            local_file_path = os.path.join(tmp_dir, os.path.basename(prefix))

            s3_client.download_file(bucket_name, prefix, local_file_path)
        except Exception as error:
            print(f"Error downloading file '{doc.path}' from S3: {error}")
            raise ValueError(f"Error downloading file '{doc.path}' from S3: {error}")

        ndb_doc = preload_chunks(
            resource_path=local_file_path,
            display_path=f"/{bucket_name}.s3.amazonaws.com/{prefix}",
            doc_id=doc.doc_id,
            metadata=doc.metadata,
            options=doc.options,
        )

        os.remove(local_file_path)

    else:

        save_artifact_uuid = str(uuid.uuid4())
        artifact_dir = os.path.join(doc_save_dir, save_artifact_uuid)
        os.makedirs(artifact_dir, exist_ok=True)
        shutil.copy(src=doc.path, dst=artifact_dir)

        ndb_doc = preload_chunks(
            resource_path=os.path.join(artifact_dir, os.path.basename(doc.path)),
            display_path=os.path.join(save_artifact_uuid, os.path.basename(doc.path)),
            doc_id=doc.doc_id,
            metadata=doc.metadata,
            options=doc.options,
        )

    with open(output_path, "wb") as file:
        pickle.dump(ndb_doc, file)
