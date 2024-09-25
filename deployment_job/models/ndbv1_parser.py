import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Response
from file_handler import FileInfo, FileLocation, create_s3_client
from thirdai import neural_db as ndb


def convert_to_ndb_file(
    file: str, metadata: Optional[Dict[str, Any]], options: Dict[str, Any]
) -> ndb.Document:
    """
    Convert a file to an NDB file type based on its extension.
    """
    filename, ext = os.path.splitext(file)

    if ext == ".pdf":
        return ndb.PDF(file, metadata=metadata, save_extra_info=False)
    elif ext == ".docx":
        return ndb.DOCX(file, metadata=metadata)
    elif ext == ".html":
        base_filename = os.path.basename(filename)

        with open(file, "r", encoding="utf-8") as f:
            html_content = f.read()

        dummy_response = Response()
        dummy_response.status_code = 200
        dummy_response._content = html_content.encode("utf-8")

        return ndb.URL(
            base_filename, dummy_response, metadata=metadata, save_extra_info=False
        )
    elif ext == ".csv":
        return ndb.CSV(
            file,
            id_column=options.get("csv_id_column", None),
            strong_columns=options.get("csv_strong_columns", None),
            weak_columns=options.get("csv_weak_columns", None),
            reference_columns=options.get("csv_reference_columns", None),
            metadata=metadata,
            save_extra_info=False,
        )
    else:
        raise TypeError(f"{ext} Document type isn't supported yet.")


def parse_doc(doc: FileInfo, tmp_dir: str) -> ndb.Document:
    """
    Process a file, downloading it from S3 if necessary, and convert it to an NDB file.
    """
    if doc.location == FileLocation.s3:
        s3 = True
        s3_client = create_s3_client()
        bucket_name, prefix = doc.path.replace("s3://", "").split("/", 1)
        local_file_path = os.path.join(tmp_dir, os.path.basename(prefix))

        # Download the file from S3
        try:
            s3_client.download_file(bucket_name, prefix, local_file_path)
        except Exception as error:
            print(
                f"There was an error downloading the file from s3 : {error}. {doc.path}"
            )
            return f"There was an error downloading the file from s3 : {error}"
    else:
        local_file_path = doc.path
        s3 = False

    # Convert to NDB file
    ndb_file = convert_to_ndb_file(
        local_file_path, metadata=doc.metadata, options=doc.options
    )

    if s3:
        ndb_file.path = Path(f"/{bucket_name}.s3.amazonaws.com/{prefix}")
        # Remove the local file
        os.remove(local_file_path)

    return ndb_file
