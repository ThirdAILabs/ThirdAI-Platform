from enum import Enum
from typing import List, Literal, Union

from platform_common.file_handler import FileInfo
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    upvote = "upvote"
    associate = "associate"
    implicit_upvote = "implicit_upvote"


class UpvoteLog(BaseModel):
    action: Literal[ActionType.upvote] = ActionType.upvote

    chunk_ids: List[int]
    queries: List[str]


class AssociateLog(BaseModel):
    action: Literal[ActionType.associate] = ActionType.associate

    sources: List[str]
    targets: List[str]


class ImplicitUpvoteLog(BaseModel):
    action: Literal[ActionType.implicit_upvote] = ActionType.implicit_upvote

    chunk_id: int
    query: str

    event_desc: str


class FeedbackLog(BaseModel):
    event: Union[UpvoteLog, AssociateLog, ImplicitUpvoteLog] = Field(
        ..., discriminator="action"
    )


class InsertLog(BaseModel):
    documents: List[FileInfo]


class DeleteLog(BaseModel):
    doc_ids: List[str]
