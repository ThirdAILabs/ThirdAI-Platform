"""
This script stress tests a deployment's search and on-prem generation components.
Before running, you should create a user account on a public instance of ThirdAI platform and create a deployment.

Example usage:
locust -f stress_test_deployment.py --host=http://your-target-host.com \
    --email david@thirdai.com --password temp123 \
    --deployment_id 573c0fce-1c10-4f68-b9da-4d610bf90f7d \
    --min_wait 10 --max_wait 30 \
    --query_file questions.csv
"""

import argparse
import json
import random
import sys
from dataclasses import dataclass
from urllib.parse import urljoin

import pandas as pd
import requests
from locust import HttpUser, TaskSet, between, task
from locust.main import main as locust_main
from requests.auth import HTTPBasicAuth


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--host", type=str)
    parser.add_argument("--deployment_id", type=str)
    parser.add_argument("--email", type=str)
    parser.add_argument("--password", type=str)
    parser.add_argument(
        "--min_wait",
        type=int,
        default=10,
        help="Minimum wait time between tasks in seconds",
    )
    parser.add_argument(
        "--max_wait",
        type=int,
        default=30,
        help="Maximum wait time between tasks in seconds",
    )
    parser.add_argument(
        "--query_file",
        type=str,
        help="The path to a csv file with a 'QUERY' column containing example queries.",
    )

    args, unknown = parser.parse_known_args()

    # Remove our custom args from sys.argv
    sys.argv = [sys.argv[0]] + unknown

    return args


args = parse_args()


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


class ModelBazaarLoadTest(TaskSet):
    df = pd.read_csv(args.query_file)
    queries = list(df["QUERY"])

    def on_start(self):
        login_details = Login.with_email(
            base_url=urljoin(args.host, "/api/"),
            email=args.email,
            password=args.password,
        )
        self.auth_token = login_details.access_token

    @task(1)
    def test_predict_and_generation(self):
        query = self.queries[random.randint(0, len(self.queries) - 1)]
        if self.auth_token:
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
            }

            response = self.client.post(
                f"/{args.deployment_id}/search",
                json={"query": query, "top_k": 5},
                headers=headers,
            )

        headers = {"Content-Type": "application/json"}

        context = " ".join(
            "\n\n".join(
                [x["text"] for x in json.loads(response.text)["data"]["references"]]
            ).split(" ")[:2000]
        )

        data = {
            "system_prompt": "You are a helpful assistant. Please be concise in your answers.",
            "prompt": f"Context: {context}, Question: {query}, Please be concise if you can. Answer: ",
            "repeat_last_n": 128,
            "n_predict": 1000,
        }

        response = self.client.post(
            "/on-prem-llm/completion",
            json=data,
            headers=headers,
        )


class WebsiteUser(HttpUser):
    tasks = [ModelBazaarLoadTest]
    wait_time = between(args.min_wait, args.max_wait)
    host = args.host


if __name__ == "__main__":
    locust_main()
