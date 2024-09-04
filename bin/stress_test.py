# Generate 66 questions on the rice pdf
# create perturbations of 33 of them
# now we have 99 total questions

# 33 without perturbations in cache
# 33 with perturbations not in cache
# 33 without perturbations not in cache

# at the beginning, insert the 33 without perturbations in cache into the cache

# we should now hit the cache and if it is a success we return, otherwise we go to generation
# we should cache the generated response


import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from urllib.parse import urljoin

import pandas as pd
import requests
import websockets
from locust import HttpUser, TaskSet, between, events, task  # type: ignore
from requests.auth import HTTPBasicAuth


def run_async(coroutine):
    return asyncio.new_event_loop().run_until_complete(coroutine)


@dataclass
class Login:
    base_url: str
    username: str
    access_token: str

    @staticmethod
    def with_email(base_url: str, email: str, password: str):
        # Perform email login using HTTPBasicAuth
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


# Global counters for success and failure
success_count = 0
failure_count = 0


@events.request.add_listener
def request_listener(
    request_type,
    name,
    response_time,
    response_length,
    response,
    context,
    exception,
    **kwargs,
):
    global success_count, failure_count
    # Check if the response status code is between 200 and 300
    if 200 <= response.status_code < 300:
        success_count += 1
    else:
        failure_count += 1


deployment_id = "7c4475de-a9c5-4166-a103-893b50c6d4ff"


class ModelBazaarLoadTest(TaskSet):
    df = pd.read_csv("questions.csv")
    in_cache = list(df.in_cache)
    perturbed = list(df.perturbed)
    new_queries = list(df.new_queries)
    queries = in_cache + perturbed + new_queries

    def on_start(self):
        login_details = Login.with_email(
            base_url="http://40.69.173.69:80/api/",
            email="david@thirdai.com",
            password="temp123",
        )
        self.auth_token = login_details.access_token

        # TODO insert the selected queries into the cache
        # as a workaround I can manually insert the ones into the cache

    @task(1)
    def test_generation(self):
        import random

        query = self.queries[random.randint(0, len(self.queries) - 1)]
        if self.auth_token:
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
            }
            base_params = {"query": query, "top_k": 5}
            ndb_params = {"constraints": {}}

            response = self.client.post(
                f"/{deployment_id}/predict",
                json={"base_params": base_params, "ndb_params": ndb_params},
                headers=headers,
            )

        headers = {"Content-Type": "application/json"}

        context = " ".join(
            "\n\n".join(
                [x["text"] for x in json.loads(response.text)["data"]["references"]]
            ).split(" ")[:2000]
        )
        # print(context)
        data = {
            "system_prompt": "You are a helpful assistant. Please be concise in your answers.",
            "prompt": f"Context: {context}, Question: {query}, Please be concise if you can. Answer: ",
            "repeat_last_n": 128,
            "n_predict": 1000,
        }
        # data = {"prompt": query + " Please be concise if you can."}

        print("starting request")
        response = self.client.post(
            "/on-prem-llm/completion",
            json=data,
            headers=headers,
        )
        # print("done", len(response.text))

        # with self.client.post("/on-prem-llm/completion", headers=headers, json=data, stream=True) as response:
        #     for chunk in response.iter_content(chunk_size=8192):
        #         if chunk:
        #             print(chunk.decode("utf-8"))

    def on_stop(self):
        global success_count, failure_count
        print(f"Total Successes: {success_count}")
        print(f"Total Failures: {failure_count}")


class WebsiteUser(HttpUser):
    tasks = [ModelBazaarLoadTest]
    wait_time = between(10, 30)


if __name__ == "__main__":

    os.system("locust -f stress_test.py --host=http://40.69.173.69:80")
