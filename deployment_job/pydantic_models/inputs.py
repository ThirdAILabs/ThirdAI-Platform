"""
Defines input models for Pydantic validation and utility functions for conversions.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from file_handler import FileInfo
from pydantic import BaseModel, Field
from pydantic_models.constraints import Constraints


class NDBSearchParams(BaseModel):
    """
    Represents extra parameters for NDB search queries.
    """

    query: str
    top_k: int = 5
    constraints: Constraints = Field(default_factory=Constraints)
    rerank: bool = False
    context_radius: int = 1


class TextAnalysisPredictParams(BaseModel):
    """
    Represents the base query parameters.
    """

    text: str
    top_k: int = 5


class AssociateInputSingle(BaseModel):
    """
    Represents a single source-target pair for association.
    """

    source: str
    target: str


class AssociateInput(BaseModel):
    """
    Represents a list of source-target pairs for association.
    """

    text_pairs: List[AssociateInputSingle]


class Reference(BaseModel):
    """
    Represents a reference result from a search query.
    """

    id: int = Field(..., ge=0)
    text: str
    context: str
    source: str
    metadata: Dict[str, Any]
    source_id: str
    score: float


class UpvoteInputSingle(BaseModel):
    """
    Represents a single query-reference pair for upvoting.
    """

    query_text: str
    reference_id: int = Field(..., ge=0)


class UpvoteInput(BaseModel):
    """
    Represents a list of query-reference pairs for upvoting.
    """

    text_id_pairs: List[UpvoteInputSingle]


class ImplicitFeedbackInput(BaseModel):
    """
    Represents a implicit feedback sample for upvoting based on user interations.
    """

    query_text: str
    reference_id: int = Field(..., ge=0)

    event_desc: str
    reference_rank: Optional[int] = Field(None, ge=0)


class SearchResultsNDB(BaseModel):
    """
    Represents the search results including the query and references.
    """

    query_text: str
    references: List[Reference]


class PiiEntity(BaseModel):
    token: str
    label: str


class EnterpriseSearchResults(BaseModel):
    """
    Represents the search results including the query and references.
    """

    query_text: str
    references: List[Reference]

    pii_entities: Optional[List[PiiEntity]] = None


class UnredactArgs(BaseModel):
    text: str
    pii_entities: List[PiiEntity]


class DocumentList(BaseModel):
    documents: List[FileInfo]


class DeleteInput(BaseModel):
    """
    Represents a list of source IDs to be deleted.
    """

    source_ids: List[str]


class SearchResultsTextClassification(BaseModel):
    query_text: str
    predicted_classes: List[Tuple[str, float]]


class SearchResultsTokenClassification(BaseModel):
    query_text: str
    tokens: List[str]
    predicted_tags: List[List[str]]


class SaveModel(BaseModel):
    """
    Represents the parameters for saving a model.
    """

    override: bool
    model_name: Optional[str] = None

    class Config:
        protected_namespaces = ()


def convert_reference_to_pydantic(input: Any, context_radius: int) -> Reference:
    """
    Converts a reference object to a Pydantic Reference model.

    Args:
        input: The input reference object.
        context_radius: The context radius for the reference.

    Returns:
        Reference: The Pydantic Reference model.
    """

    def convert_to_json_encodable(value: Any) -> str:
        try:
            return json.dumps(value)
        except TypeError:
            return str(value)

    return Reference(
        id=input.id,
        text=input.text,
        source=input.source,
        metadata={k: convert_to_json_encodable(v) for k, v in input.metadata.items()},
        context=input.context(radius=context_radius),
        source_id=input.document.hash,
        score=input.score,
    )


class ChatInput(BaseModel):
    user_input: str
    session_id: Optional[str] = None
    provider: str = "openai"


class ChatHistoryInput(BaseModel):
    session_id: Optional[str] = None
    provider: str = "openai"


class ChatSettings(BaseModel):
    top_k: int = 5
    model: str = "gpt-4o-mini"
    provider: str = "openai"
    key: str = None
    temperature: float = 0.2
    chat_prompt: str = "Answer the user's questions based on the below context:"
    query_reformulation_prompt: str = (
        "Given the above conversation, generate a search query that would help retrieve relevant sources for responding to the last message."
    )
