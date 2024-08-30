from locust import HttpUser, TaskSet, between, task


class MyTaskSet(TaskSet):

    import pandas as pd

    df = pd.read_csv("squad.csv")
    queries = list("Context: " + df.context + "\n Question: " + df.question)

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


class MyUser(HttpUser):
    tasks = [MyTaskSet]
    wait_time = between(60, 70)


