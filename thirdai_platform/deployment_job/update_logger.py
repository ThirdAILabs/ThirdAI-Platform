import os
import uuid
from enum import Enum
from typing import List, Literal, Union

from pydantic import BaseModel, Field

from thirdai_platform.platform_common.file_handler import FileInfo


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


class UpdateLogger:
    def __init__(self, log_dir):
        os.makedirs(log_dir, exist_ok=True)
        # We use a UUID here so that each autoscaling allocation has a distinct file.
        log_file = os.path.join(log_dir, f"{uuid.uuid4()}.jsonl")
        self.stream = open(log_file, "a")

    def log(self, update: BaseModel):
        self.stream.write(update.model_dump_json() + "\n")
        self.stream.flush()

    @staticmethod
    def get_feedback_logger(deployment_dir: str):
        return UpdateLogger(os.path.join(deployment_dir, "feedback"))

    @staticmethod
    def get_insertion_logger(deployment_dir: str):
        return UpdateLogger(os.path.join(deployment_dir, "insertions"))

    @staticmethod
    def get_deletion_logger(deployment_dir: str):
        return UpdateLogger(os.path.join(deployment_dir, "deletions"))
