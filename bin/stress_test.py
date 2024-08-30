import json
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from locust import HttpUser, TaskSet, between, events, task  # type: ignore
from requests.auth import HTTPBasicAuth
import pandas as pd


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


deployment_id = "ca29f228-23fd-4294-8f24-96eab96ba669"


class ModelBazaarLoadTest(TaskSet):
    df = pd.read_csv("questions.csv")
    queries = list(df.questions)

    def on_start(self):
        # Perform the email login using the Login class
        login_details = Login.with_email(
            base_url="http://localhost:80/api/",  # Update this to your base URL
            email="yash@thirdai.com",
            password="password",
        )
        self.auth_token = login_details.access_token

    @task(3)
    def test_prediction(self):
        if self.auth_token:
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
            }
            base_params = {"query": "thirdai", "top_k": 5}
            ndb_params = {"constraints": {}}

            response = self.client.post(
                f"/{deployment_id}/predict",
                json={"base_params": base_params, "ndb_params": ndb_params},
                headers=headers,
            )
    
    @task(1)
    def test_sources(self):
        if self.auth_token:
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
            }

            response = self.client.get(
                f"/{deployment_id}/sources",
                headers=headers,
            )
            
    @task(2)
    def test_associate(self):
        if self.auth_token:
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
            }
            text_pairs =[
                {"source": "authors", "target": "contributors"},
                {"source": "paper", "target": "document"},
            ]

            response = self.client.post(
                f"/{deployment_id}/associate",
                json={"text_pairs": text_pairs},
                headers=headers,
            )

    def on_stop(self):
        global success_count, failure_count
        # Log the counts when the test stops
        print(f"Total Successes: {success_count}")
        print(f"Total Failures: {failure_count}")

    @task
    def test_api_endpoint(self):
        import random

        headers = {"Content-Type": "application/json"}

        data = {"query": self.queries[random.randint(0, len(self.queries) - 1)]}

        with self.client.post(
            "/on-prem-llm/generate",
            json=data,
            headers=headers,
            stream=True,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                # Process the streamed content
                try:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            # You can process each chunk here, or just read through it
                            pass
                    response.success()
                except Exception as e:
                    response.failure(f"Failed to process streaming response: {str(e)}")
            else:
                response.failure(
                    f"Failed with status code: {response.status_code}, Response: {response.text}"
                )


class WebsiteUser(HttpUser):
    tasks = [ModelBazaarLoadTest]
    wait_time = between(2, 3)  # Adjust as needed to increase concurrency


if __name__ == "__main__":
    import os

    os.system("locust -f stress_test.py --host=http://localhost:80")