import os

pass
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import List, Literal, Union

from file_handler import FileInfo
from pydantic import BaseModel, Field
from utils import save_json


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
    timestamp: str = datetime.now().strftime("%Y-%m-%d %H-%M-%S")


class InsertLog(BaseModel):
    documents: List[FileInfo]


class DeleteLog(BaseModel):
    doc_ids: List[str]


class UpdateLogger:
    def __init__(self, log_dir, update_stats_after: int = 50):
        # We use NOMAD_ALLOC_ID here so that each autoscaling allocation has a distinct file.
        self.log_dir = os.path.join(log_dir, f'alloc_{os.getenv("NOMAD_ALLOC_ID")}')
        os.makedirs(self.log_dir, exist_ok=True)
        log_file = os.path.join(self.log_dir, "events.jsonl")
        self.stream = open(log_file, "a")

        self.update_stats_after = update_stats_after
        self.stats_tracker = defaultdict(list)
        self.num_lines = 0

    def log(self, update: BaseModel, update_stat_immediately: bool = True):
        self.stream.write(update.model_dump_json() + "\n")
        self.stream.flush()
        if isinstance(update, FeedbackLog):
            self.num_lines += 1
            self._update_track(update, update_stat_immediately)

    def _update_track(self, update: BaseModel, update_stat_immediately: bool = True):
        action = update.event.action
        self.stats_tracker[action].append(update.model_dump())

        if update_stat_immediately or (self.num_lines % self.update_stats_after == 0):
            save_json(self._get_tracker_loc(), self.stats_tracker)

        if self.num_lines % self.update_stats_after == 0:
            self.stats_tracker = defaultdict(list)

    def _get_tracker_loc(self):
        return os.path.join(self.log_dir, "last_stats.json")

    @staticmethod
    def get_feedback_logger(deployment_dir: str, update_stats_after: int = 50):
        return UpdateLogger(
            os.path.join(deployment_dir, "feedback"), update_stats_after
        )

    @staticmethod
    def get_insertion_logger(deployment_dir: str, update_stats_after: int = 50):
        return UpdateLogger(
            os.path.join(deployment_dir, "insertions"), update_stats_after
        )

    @staticmethod
    def get_deletion_logger(deployment_dir: str, update_stats_after: int = 50):
        return UpdateLogger(
            os.path.join(deployment_dir, "deletions"), update_stats_after
        )

    def __del__(self):
        self.stream.close()
