import ast
import datetime
import enum
import re
from typing import Tuple

import fitz
import requests
from thirdai import neural_db as ndb


def now() -> str:
    """
    Returns the current UTC time without microseconds.

    Returns:
        str: Current UTC time in iso format.
    """
    return (
        datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    )


def delete_deployment_job(
    nomad_endpoint: str, model_id: str, task_runner_token: str
) -> Tuple[requests.Response, str]:
    """
    Deletes a job from Nomad.

    Args:
        model_id (str): The model ID.
        task_runner_token (str): The task runner token.

    Returns:
        Tuple[requests.Response, str]: The response from the delete request and the job ID.
    """
    job_id = f"deployment-{model_id}"
    job_url = f"{nomad_endpoint}/v1/job/{job_id}"
    headers = {"X-Nomad-Token": task_runner_token}
    response = requests.delete(job_url, headers=headers)
    return response, job_id


def validate_name(name: str) -> None:
    """
    Validates a name to ensure it matches a specific regex pattern.

    Args:
        name (str): The name to validate.

    Raises:
        ValueError: If the name does not match the regex pattern.
    """
    regex_pattern = "^[\w-]+$"
    if not re.match(regex_pattern, name):
        raise ValueError("name is not valid")


class Status(str, enum.Enum):
    not_started = "not_started"
    starting = "starting"
    in_progress = "in_progress"
    stopped = "stopped"
    complete = "complete"
    failed = "failed"


def highlighted_pdf_bytes(reference: ndb.Reference):
    """
    Generate highlighted PDF bytes from a reference.

    Parameters:
    - reference: ndb.Reference - The document reference containing metadata and source path.

    Returns:
    - bytes: The PDF with highlights as bytes, or None if no highlights are present.
    """
    if "highlight" not in reference.metadata:
        return None
    highlight = ast.literal_eval(reference.metadata["highlight"])
    doc = fitz.open(reference.source)
    for key, val in highlight.items():
        page = doc[key]
        blocks = page.get_text("blocks")
        for i, b in enumerate(blocks):
            if i in val:
                rect = fitz.Rect(b[:4])
                page.add_highlight_annot(rect)
    return doc.tobytes()


def new_pdf_chunks(db: ndb.NeuralDB, reference: ndb.Reference):
    """
    Get chunks of a PDF document with text and bounding boxes for each chunk.

    Parameters:
    - db: ndb.NeuralDB - The database instance.
    - reference: ndb.Reference - The document reference containing metadata and source path.

    Returns:
    - dict: A dictionary containing filename, ids, text, and bounding boxes for each chunk, or None if no chunk boxes are present.
    """
    if "chunk_boxes" not in reference.metadata:
        return None
    doc, start_id = db._savable_state.documents._get_doc_and_start_id(reference.id)
    ids = list(range(start_id, start_id + doc.table.size))
    rows = doc.table.iter_rows_as_dicts()
    text_and_boxes = [(row["display"], eval(row["chunk_boxes"])) for _, row in rows]
    return {
        "filename": reference.source,
        "id": ids,
        "text": [text for text, _ in text_and_boxes],
        "boxes": [boxes for _, boxes in text_and_boxes],
    }


def old_pdf_chunks(db: ndb.NeuralDB, reference: ndb.Reference):
    """
    Get chunks of a PDF document with text and highlighted bounding boxes for each chunk.

    Parameters:
    - db: ndb.NeuralDB - The database instance.
    - reference: ndb.Reference - The document reference containing metadata and source path.

    Returns:
    - dict: A dictionary containing filename, ids, text, and bounding boxes for each chunk, or None if no highlights are present.
    """
    if "highlight" not in reference.metadata:
        return None
    doc, start_id = db._savable_state.documents._get_doc_and_start_id(reference.id)
    doc: ndb.PDF = doc
    ids = list(range(start_id, start_id + doc.table.size))
    rows = doc.table.iter_rows_as_dicts()
    text_and_highlights = [(row["display"], eval(row["highlight"])) for _, row in rows]
    doc = fitz.open(reference.source)
    page_blocks = [page.get_text("blocks") for page in doc]
    boxes = [
        [
            (page_idx, page_blocks[page_idx][i][:4])
            for page_idx, block_ids in highlight.items()
            for i in block_ids
        ]
        for _, highlight in text_and_highlights
    ]
    return {
        "filename": reference.source,
        "id": ids,
        "text": [text for text, _ in text_and_highlights],
        "boxes": boxes,
    }
