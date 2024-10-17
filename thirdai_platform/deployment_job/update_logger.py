import os
import uuid

from pydantic import BaseModel


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
