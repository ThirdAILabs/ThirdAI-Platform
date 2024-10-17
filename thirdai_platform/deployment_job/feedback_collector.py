import json
import os
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Union

from pydantic_models.inputs import AssociateInput, UpvoteInput


class FeedbackCollector:
    def __init__(
        self, log_dir: Path, track_last_n: int = 50, write_after_updates: int = 50
    ):
        os.makedirs(log_dir, exist_ok=True)
        self._log_file = os.path.join(log_dir, f"{os.getenv('NOMAD_ALLOC_ID')}.json")
        self._queue = defaultdict(deque(maxlen=track_last_n))
        self.write_after_updates = write_after_updates
        self.update_counter = 0

    def add(self, input: Union[AssociateInput, UpvoteInput]):
        if isinstance(input, AssociateInput):
            event = "associate"
        elif isinstance(input, UpvoteInput):
            event = "upvote"
        else:
            raise ValueError("input type not supported")

        feedback = input.model_dump()
        feedback["timestamp"] = str(datetime.now())
        self._queue[event].append(feedback)
        self.update_counter += 1

        if self.update_counter % self.write_after_updates == 0:
            # write updates to jsonl file
            with open(self._log_file, "w") as fp:
                json.dump(self._queue, fp, indent=4)

            # reset update counter
            self.update_counter = 0

    @staticmethod
    def get_feedback_logger(deployment_dir: str):
        return FeedbackCollector(os.path.join(deployment_dir, "recent_feedbacks"))
