import os
import shutil
import uuid
from typing import Any, Dict, Optional, Tuple

from fastapi import Response
from thirdai import neural_db_v2 as ndbv2

from platform_common.file_handler import FileInfo, FileLocation, create_s3_client


def convert_to_ndb_doc(
    resource_path: str,
    display_path: str,
    doc_id: Optional[str],
    metadata: Optional[Dict[str, Any]],
    options: Dict[str, Any],
) -> ndbv2.Document:
    filename, ext = os.path.splitext(resource_path)

    if ext == ".pdf":
        return ndbv2.PDF(
            resource_path,
            doc_metadata=metadata,
            display_path=display_path,
            doc_id=doc_id,
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
    Process a file, downloading it from S3 if necessary, and convert it to an NDB file.
    """
    if doc.location == FileLocation.s3:
        try:
            s3_client = create_s3_client()
            bucket_name, prefix = doc.path.replace("s3://", "").split("/", 1)
            local_file_path = os.path.join(tmp_dir, os.path.basename(prefix))

            s3_client.download_file(bucket_name, prefix, local_file_path)
        except Exception as error:
            print(f"Error downloading file '{doc.path}' from s3 : {error}")
            raise ValueError(f"Error downloading file '{doc.path}' from s3 : {error}")

        ndb_doc = preload_chunks(
            resource_path=local_file_path,
            display_path=f"/{bucket_name}.s3.amazonaws.com/{prefix}",
            doc_id=doc.doc_id,
            metadata=doc.metadata,
            options=doc.options,
        )

        os.remove(local_file_path)
        return ndb_doc

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
