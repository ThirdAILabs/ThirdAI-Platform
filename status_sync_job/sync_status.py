import os
import time
import requests
from urllib.parse import urljoin
from typing import Optional, Dict


def make_request(api: str, method: str, suffix: str, *args, **kwargs) -> Optional[Dict]:
    """
    Make an HTTP request with the given method and URL suffix.
    Args:
        method (str): HTTP method (e.g., 'post', 'get').
        suffix (str): URL suffix to append to the base API URL.
        *args: Additional positional arguments for the request.
        **kwargs: Additional keyword arguments for the request.
    Returns:
        Optional[Dict]: Parsed JSON response content if successful, None otherwise.
    """
    # Add custom user-agent to avoid ngrok abuse page
    if "headers" not in kwargs:
        kwargs["headers"] = {}

    kwargs["headers"].update({"User-Agent": "Status Sync Job"})

    url = urljoin(api, suffix)
    try:
        response = requests.request(method, url, *args, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exception:
        print(exception)
        raise exception


# TODO can we make this interval a configurable option?
# TODO how do we break out of here? is the only way to do it to kill the job?
def sync_status(interval_seconds = 15):
    backend_endpoint = os.getenv("MODEL_BAZAAR_ENDPOINT")

    if backend_endpoint is None:
        raise ValueError("Could not read MODEL_BAZAAR_ENDPOINT.")

    while True:
        time.sleep(interval_seconds)

        print("HAHAHAHAHAHA LETS GO", flush=True)

        content = make_request(
            api=backend_endpoint,
            method="post",
            suffix="api/train/sync-status",
        )

        print(content)


if __name__ == "__main__":
    print("IN SYNC STATUS JOB", flush=True)
    sync_status()