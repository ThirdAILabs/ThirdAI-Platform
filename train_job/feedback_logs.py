from enum import Enum
from typing import List, Literal, Union

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    upvote = "upvote"
    associate = "associate"


class UpvoteLog(BaseModel):
    action: Literal[ActionType.upvote] = ActionType.upvote

    chunk_ids: List[int]
    queries: List[str]


class AssociateLog(BaseModel):
    action: Literal[ActionType.associate] = ActionType.associate

    sources: List[str]
    targets: List[str]


class FeedbackLog(BaseModel):
    event: Union[UpvoteLog, AssociateLog] = Field(..., discriminator="action")
