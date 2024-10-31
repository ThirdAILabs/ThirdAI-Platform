"""
To run this file do:
    `locust -f stress_test_deployment.py`
which will spin up the web UI to configure tests. 
You can also use the --headless flag to skip the UI. 

To run locust distributed on blade you can run this script with the --master flag
    `locust -f stress_test_deployment.py --master`
Which starts the master process.

Then on any node you want you can do something like:
    ```
    for i in {1..48}; do
    locust -f - --worker --master-host=192.168.1.6 &
    done
    ```
to spin up 48 workers in the background. The master host is node 6 in this case.

Please note, each node must have a separate environment with the same version of
locust installed. It also didn't work in python 3.8 for me for some reason.

Running `pip3 install locust --upgrade --no-cache-dir --force-reinstall` on each
node should do the trick.
"""

import argparse
import json
import os
import random
import sys
import uuid
from dataclasses import dataclass
from urllib.parse import urljoin

import pandas as pd
import requests
from locust import HttpUser, TaskSet, between, task
from requests.auth import HTTPBasicAuth


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--host", type=str, default="http://localhost:80")
    parser.add_argument("--deployment_id", type=str)
    parser.add_argument("--email", type=str)
    parser.add_argument("--password", type=str)
    parser.add_argument("--query_file", type=str)
    parser.add_argument(
        "--min_wait",
        type=int,
        default=10,
        help="Minimum wait time between tasks in seconds",
    )
    parser.add_argument(
        "--max_wait",
        type=int,
        default=20,
        help="Maximum wait time between tasks in seconds",
    )
    parser.add_argument("--predict_weight", type=int, default=20)
    parser.add_argument("--insert_weight", type=int, default=2)
    parser.add_argument("--delete_weight", type=int, default=1)
    parser.add_argument("--upvote_weight", type=int, default=2)
    parser.add_argument("--associate_weight", type=int, default=2)
    parser.add_argument("--sources_weight", type=int, default=5)
    parser.add_argument("--save_weight", type=int, default=1)
    parser.add_argument("--implicit_feedback_weight", type=int, default=10)

    # Generation is a separate test
    parser.add_argument("--generation", type=bool, default=False)
    parser.add_argument("--chat_weight", type=int, default=1)
    parser.add_argument("--generate_weight", type=int, default=1)

    args, unknown = parser.parse_known_args()

    # Remove our custom args from sys.argv
    sys.argv = [sys.argv[0]] + unknown

    return args


args = parse_args()

queries = list(pd.read_csv(args.query_file)["query"])


# Note: this code is copied here to make running locust with distributed easier.
# Locust has builtin logic to copy this file over to the child node every run
@dataclass
class Login:
    base_url: str
    username: str
    access_token: str

    @staticmethod
    def with_email(base_url: str, email: str, password: str):
        response = requests.get(
            urljoin(base_url, "user/email-login"),
            auth=HTTPBasicAuth(email, password),
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise Exception(f"Login failed: {response.status_code}, {response.text}")
        content = json.loads(response.content)
        username = content["data"]["user"]["username"]
        access_token = content["data"]["access_token"]
        return Login(base_url, username, access_token)


def random_query():
    return random.choice(queries)


def route(name):
    return f"/{args.deployment_id}/{name}"


login_details = Login.with_email(
    base_url=urljoin(args.host, "/api/"),
    email=args.email,
    password=args.password,
)

username = login_details.username
auth_header = {"Authorization": f"Bearer {login_details.access_token}"}

# TODO
# each test should have a folder with queries, original documents, and documents to add
# error handling


class NeuralDBLoadTest(TaskSet):
    @task(args.predict_weight)
    def test_predict(self):
        query = random_query()

        response = self.client.post(
            route("search"),
            json={"query": query, "top_k": 5},
            headers=auth_header,
            timeout=60,
        )

    @task(args.insert_weight)
    def test_insert(self):
        def doc_dir():
            return "/home/david/ThirdAI-Platform/thirdai_platform/train_job/sample_docs"

        documents = [
            {"path": "mutual_nda.pdf", "location": "local"},
            {"path": "four_english_words.docx", "location": "local"},
            {"path": "supervised.csv", "location": "local"},
        ]

        files = [
            *[
                ("files", open(os.path.join(doc_dir(), doc["path"]), "rb"))
                for doc in documents
            ],
            (
                "documents",
                (None, json.dumps({"documents": documents}), "application/json"),
            ),
        ]

        res = self.client.post(
            route("insert"),
            files=files,
            headers=auth_header,
        )

    @task(args.delete_weight)
    def test_delete(self):
        response = self.client.get(route("sources"), headers=auth_header)

        # always delete the most recently added source so we reduce the chance
        # of deleting the original data and returning no results with queries
        source_id = response.json()["data"][-1]["source_id"]

        self.client.post(
            route("delete"),
            json={"source_ids": [source_id]},
            headers=auth_header,
        )

    @task(args.upvote_weight)
    def test_upvote(self):
        query = random_query()

        response = self.client.post(
            route("search"),
            json={"query": query, "top_k": 5},
            headers=auth_header,
            timeout=60,
        )

        ref_id = response.json()["data"]["references"][-1]["id"]
        text_id_pairs = [{"query_text": query, "reference_id": ref_id}]

        self.client.post(
            route("upvote"),
            json={"text_id_pairs": text_id_pairs},
            headers=auth_header,
        )

    @task(args.associate_weight)
    def test_associate(self):
        query1 = random_query()
        query2 = random_query()
        text_pairs = [{"source": query1, "target": query2}]
        self.client.post(
            route("associate"),
            json={"text_pairs": text_pairs},
            headers=auth_header,
        )

    @task(args.sources_weight)
    def test_sources(self):
        res = self.client.get(route("sources"), headers=auth_header)

    @task(args.implicit_feedback_weight)
    def test_implicit_feedback(self):
        query = random_query()

        response = self.client.post(
            route("search"),
            json={"query": query, "top_k": 5},
            headers=auth_header,
            timeout=60,
        )

        ref_id = response.json()["data"]["references"][-1]["id"]
        feedback = {
            "query_text": query,
            "reference_id": ref_id,
            "event_desc": "reference click",
        }

        res = self.client.post(
            route("implicit-feedback"), json=feedback, headers=auth_header
        )

    @task(args.save_weight)
    def test_save(self):
        model_name = str(uuid.uuid4())
        res = self.client.post(
            route("save"),
            json={"override": False, "model_name": model_name},
            headers=auth_header,
        )

        self.client.post(
            "/api/model/delete",
            params={"model_identifier": f"{username}/{model_name}"},
            headers=auth_header,
        )


class GenerationLoadTest(TaskSet):
    @task(args.chat_weight)
    def test_chat(self):
        query = random_query()

        response = self.client.post(
            route("chat"),
            json={"user_input": query},
            headers=auth_header,
            timeout=60,
        )

    @task(args.generate_weight)
    def test_search_and_generate(self):
        query = random_query()

        response = self.client.post(
            route("search"),
            json={"query": query, "top_k": 5},
            headers=auth_header,
            timeout=60,
        )

        references = [
            {"text": x["text"], "source": x["source"]}
            for x in response.json()["data"]["references"]
        ]

        response = self.client.post(
            f"/llm-dispatch/generate",
            json={
                "query": query,
                "references": references,
                "key": os.getenv("GENAI_KEY"),
            },
            headers=auth_header,
            timeout=60,
        )


class WebsiteUser(HttpUser):
    tasks = [NeuralDBLoadTest]
    if args.generation:
        tasks.append(GenerationLoadTest)
    wait_time = between(args.min_wait, args.max_wait)
    host = args.host
