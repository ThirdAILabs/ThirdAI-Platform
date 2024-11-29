import json
import os
import time
from typing import List
from urllib.parse import urljoin

from client.clients import Login
from client.utils import (
    auth_header,
    http_delete_with_error,
    http_get_with_error,
    http_post_with_error,
)


class KnowledgeExtraction:
    def __init__(self, url: str, email: str, password: str):
        if not url.endswith("/"):
            url += "/"
        self.base_url = urljoin(url, "api/")
        self.login = Login.with_email(
            base_url=self.base_url, email=email, password=password
        )

        self.model_name = None
        self.model_id = None

        self.deployment_url = None

    def create(self, model_name: str, questions: List[str], llm_provider: str):
        res = http_post_with_error(
            urljoin(self.base_url, "workflow/knowledge-extraction"),
            headers=auth_header(self.login.access_token),
            json={
                "model_name": model_name,
                "questions": [{"question": q} for q in questions],
                "llm_provider": llm_provider,
            },
        )
        self.model_name = model_name
        self.model_id = res.json()["data"]["model_id"]

    def start(self, autoscaling: bool = True, autoscaling_max_count: int = 4):
        if not self.model_name:
            raise ValueError(
                "must call client.create(...) before calling client.start()"
            )
        http_post_with_error(
            urljoin(self.base_url, "deploy/run"),
            headers=auth_header(self.login.access_token),
            params={
                "model_identifier": f"{self.login.username}/{self.model_name}",
                "autoscaling_enabled": autoscaling,
                "autoscaler_max_count": autoscaling_max_count,
            },
        )
        self.deployment_url = urljoin(
            self.base_url.removesuffix("api/"), f"{self.model_id}/"
        )

    def wait_for_deployment(self, timeout_sec: int):
        self._check_started()

        url = urljoin(self.base_url, "deploy/status")
        params = {"model_identifier": f"{self.login.username}/{self.model_name}"}
        for _ in range(timeout_sec):
            response = http_get_with_error(
                url, params=params, headers=auth_header(self.login.access_token)
            )
            status = response.json()["data"]["deploy_status"]

            if status == "in_progress" or status == "starting":
                time.sleep(1)
            elif status == "complete":
                return
            else:
                raise ValueError(f"deployment has status '{status}'")
        raise ValueError("timeout reached before deployment completed")

    def stop(self):
        self._check_started()

        http_post_with_error(
            urljoin(self.base_url, "deploy/stop"),
            headers=auth_header(self.login.access_token),
            params={"model_identifier": f"{self.login.username}/{self.model_name}"},
        )

        self.deployment_url = None

    def _check_started(self):
        if not self.deployment_url:
            raise ValueError("must call client.start() before accessing this method")

    def create_report(self, files: List[str]) -> str:
        self._check_started()

        multipart = []
        for file in files:
            multipart.append(("files", open(file, "rb")))

        files = [
            {"path": os.path.basename(file), "location": "local"} for file in files
        ]
        multipart.append(
            ("documents", (None, json.dumps({"documents": files}), "application/json"))
        )

        res = http_post_with_error(
            urljoin(self.deployment_url, "report/create"),
            files=multipart,
            headers=auth_header(self.login.access_token),
        )

        return res.json()["data"]["report_id"]

    def get_report(self, report_id: str):
        self._check_started()

        res = http_get_with_error(
            urljoin(self.deployment_url, f"report/{report_id}"),
            headers=auth_header(self.login.access_token),
        )

        return res.json()["data"]

    def delete_report(self, report_id: str):
        self._check_started()

        http_delete_with_error(
            urljoin(self.deployment_url, f"report/{report_id}"),
            headers=auth_header(self.login.access_token),
        )

    def list_questions(self):
        self._check_started()

        res = http_get_with_error(
            urljoin(self.deployment_url, "questions"),
            headers=auth_header(self.login.access_token),
        )

        return res.json()["data"]

    def add_question(self, question: str):
        self._check_started()

        http_post_with_error(
            urljoin(self.deployment_url, "questions"),
            headers=auth_header(self.login.access_token),
            params={"question": question},
        )

    def delete_question(self, question_id: str):
        self._check_started()

        http_delete_with_error(
            urljoin(self.deployment_url, f"questions/{question_id}"),
            headers=auth_header(self.login.access_token),
        )

    def add_keywords(self, question_id: str, keywords: List[str]):
        self._check_started()

        http_post_with_error(
            urljoin(self.deployment_url, f"questions/{question_id}/keywords"),
            headers=auth_header(self.login.access_token),
            json=keywords,
        )
