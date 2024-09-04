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


import requests
from requests.auth import HTTPBasicAuth

response = requests.get(
    "http://40.69.173.69:80/api/user/email-login",
    auth=HTTPBasicAuth("david@thirdai.com", "temp123"),
)

import json

access_token = json.loads(response.text)["data"]["access_token"]

url = "http://40.69.173.69:80/cache/token"
headers = {
    "Authorization": f"Bearer {access_token}",
    # "Content-Type": "application/json",
}

response = requests.post(
    url, headers=headers, params={"model_id": "7c4475de-a9c5-4166-a103-893b50c6d4ff"}
)

print(response.text)


data = {"model_id": "573c0fce-1c10-4f68-b9da-4d610bf90f7d"}


import asyncio
import json

import websockets


async def connect_and_generate():
    uri = "ws://localhost/llm-dispatch/generate"  # Change to the correct WebSocket URL if needed

    # Example input message to be sent to the WebSocket
    input_message = {
        "query": "Your input text",
        "model": "Model name",
        "provider": "AI provider",
        "key": "Optional API key",  # Leave as None or empty if not needed
    }

    try:
        # Establish WebSocket connection
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket.")

            # Send input message
            await websocket.send(json.dumps(input_message))
            print(f"Sent message: {input_message}")

            # Continuously listen for messages from the server
            while True:
                response = await websocket.recv()
                response_data = json.loads(response)

                # Process the response
                print(f"Received response: {response_data}")

                # Check for "end_of_stream"
                if response_data.get("end_of_stream", False):
                    print("End of stream reached. Closing connection.")
                    break

    except websockets.ConnectionClosed as e:
        print(f"Connection closed with error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


# Run the async function
asyncio.run(connect_and_generate())
