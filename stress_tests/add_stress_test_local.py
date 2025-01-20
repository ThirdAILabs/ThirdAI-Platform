"""
To run this file do:
    `locust -f stress_test_deployment.py --host=http://52.53.207.253:8000 --query_file=path_to_queries.csv`
    which will spin up the web UI to configure tests.
    You can also use the --headless flag to skip the UI.

To run Locust distributed on multiple nodes, follow these steps:

1. **Start the Master Node**:
    ```bash
    locust -f stress_test_deployment.py --master --host=http://52.53.207.253:8000 --query_file=path_to_queries.csv
    ```
    This starts the master process.

2. **Start Worker Nodes**:
    On each worker node, run:
    ```bash
    locust -f stress_test_deployment.py --worker --master-host=master_ip_address --host=http://52.53.207.253:8000 --query_file=path_to_queries.csv &
    ```
    Replace `master_ip_address` with the IP address of your master node. This command spins up workers in the background.

**Note**:
- Each node must have a separate environment with the same version of Locust installed.
- It may not work with Python 3.8. Use Python 3.9 or higher.
- Install Locust using:
    ```bash
    pip3 install locust --upgrade --no-cache-dir --force-reinstall
    ```
"""

import argparse
import os
import random
import sys
import pandas as pd
from locust import HttpUser, TaskSet, between, task


def parse_args():
    parser = argparse.ArgumentParser(
        description="Locust load testing for NeuralDB /search endpoint."
    )
    parser.add_argument(
        "--host",
        type=str,
        required=True,
        help="Target host for the Locust test. Must include the scheme (http:// or https://). Example: http://52.53.207.253:8000",
    )
    parser.add_argument(
        "--query_file",
        type=str,
        required=True,
        help="Path to the CSV file containing queries.",
    )
    parser.add_argument(
        "--min_wait",
        type=int,
        default=10,
        help="Minimum wait time between tasks in seconds.",
    )
    parser.add_argument(
        "--max_wait",
        type=int,
        default=20,
        help="Maximum wait time between tasks in seconds.",
    )
    parser.add_argument(
        "--predict_weight", type=int, default=1, help="Weight for the predict task."
    )

    args, unknown = parser.parse_known_args()

    # Remove our custom args from sys.argv to prevent conflicts with Locust's own arguments
    sys.argv = [sys.argv[0]] + unknown

    return args


args = parse_args()

# Load queries from the specified CSV file
try:
    queries_df = pd.read_csv(args.query_file)
    if "query" not in queries_df.columns:
        raise ValueError("The query file must contain a 'query' column.")
    queries = queries_df["query"].dropna().tolist()
    if not queries:
        raise ValueError("The query file is empty after removing NaN values.")
except Exception as e:
    print(f"Error reading query file: {e}")
    sys.exit(1)


def random_query():
    return random.choice(queries)


def route(name):
    return f"/{name}"


def log_request_error(response):
    if response.status_code >= 400:
        print(f"Error {response.status_code}: {response.text}")


class NeuralDBLoadTest(TaskSet):
    @task
    def test_predict(self):
        query = random_query()

        payload = {
            "query": query,
            "top_k": 5,
            "constraints": {"max_length": 100, "min_length": 10},
            "rerank": False,
            "context_radius": 1,
        }

        try:
            response = self.client.post(
                route("search"),
                json=payload,
                timeout=60,
            )
            log_request_error(response)
        except Exception as e:
            print(f"Request failed: {e}")


class WebsiteUser(HttpUser):
    tasks = [NeuralDBLoadTest]
    wait_time = between(args.min_wait, args.max_wait)
    host = args.host
