"""
Defines document models for Pydantic validation.
"""

from enum import Enum
from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field, RootModel
from typing_extensions import Annotated


class DocumentLocation(str, Enum):
    """
    Enumeration of document storage locations.
    """

    LOCAL = "local"
    NFS = "nfs"
    S3 = "s3"


class Document(BaseModel):
    """
    Base class for all document types.
    """

    location: DocumentLocation = DocumentLocation.LOCAL
    on_disk: bool = True


class PDF(Document):
    """
    Represents a PDF document.
    """

    document_type: Literal["PDF"]
    path: str
    metadata: Optional[dict[str, Any]] = None
    version: str = "v1"
    chunk_size: int = 100
    stride: int = 40
    emphasize_first_words: int = 0
    ignore_header_footer: bool = True
    ignore_nonstandard_orientation: bool = True
    save_extra_info: bool = False


class CSV(Document):
    """
    Represents a CSV document.
    """

    document_type: Literal["CSV"]
    path: str
    id_column: Optional[str] = None
    strong_columns: Optional[List[str]] = None
    weak_columns: Optional[List[str]] = None
    reference_columns: Optional[List[str]] = None
    save_extra_info: bool = False
    metadata: Optional[dict[str, Any]] = None
    has_offset: bool = False


class DOCX(Document):
    """
    Represents a DOCX document.
    """

    document_type: Literal["DOCX"]
    path: str
    metadata: Optional[dict[str, Any]] = None


class URL(Document):
    """
    Represents a URL document.
    """

    document_type: Literal["URL"]
    url: str
    save_extra_info: bool = False
    title_is_strong: bool = False
    metadata: Optional[dict[str, Any]] = None


class SentenceLevelPDF(Document):
    """
    Represents a sentence-level PDF document.
    """

    document_type: Literal["SentenceLevelPDF"]
    path: str
    metadata: Optional[dict[str, Any]] = None
    save_extra_info: bool = False


class SentenceLevelDOCX(Document):
    """
    Represents a sentence-level DOCX document.
    """

    document_type: Literal["SentenceLevelDOCX"]
    path: str
    metadata: Optional[dict[str, Any]] = None


class Unstructured(Document):
    """
    Represents an unstructured document.
    """

    document_type: Literal["Unstructured"]
    path: str
    save_extra_info: bool = False
    metadata: Optional[dict[str, Any]] = None


class InMemoryText(Document):
    """
    Represents an in-memory text document.
    """

    document_type: Literal["InMemoryText"]
    name: str
    texts: list[str]
    metadatas: Optional[list[dict[str, Any]]] = None
    global_metadata: Optional[dict[str, Any]] = None


class DocumentList(RootModel):
    """
    Root model for a list of documents.
    """

    root: List[
        Annotated[
            Union[
                PDF,
                CSV,
                DOCX,
                URL,
                SentenceLevelPDF,
                SentenceLevelDOCX,
                Unstructured,
                InMemoryText,
            ],
            Field(discriminator="document_type"),
        ],
    ] = []
