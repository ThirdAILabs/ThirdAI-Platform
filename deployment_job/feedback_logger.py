import os
import uuid
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


class FeedbackLogger:
    def __init__(self, deployment_dir):
        log_dir = os.path.join(deployment_dir, "feedback")
        os.makedirs(log_dir, exist_ok=True)
        filename = os.path.join(log_dir, f"{uuid.uuid4()}.jsonl")

        self.stream = open(filename, "a")

    def log(self, event: FeedbackLog):
        self.stream.write(event.model_dump_json() + "\n")
