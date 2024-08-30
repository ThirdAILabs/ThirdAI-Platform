from abc import ABC, abstractmethod
from typing import Dict, Optional
from urllib.parse import urljoin

import requests


class Reporter(ABC):
    @abstractmethod
    def report_complete(self, model_id: str, metadata: Dict[str, str]):
        raise NotImplementedError

    @abstractmethod
    def report_status(self, model_id: str, status: str, message: str = ""):
        raise NotImplementedError


class HttpReporter(Reporter):
    def __init__(self, api_url: str):
        """
        Initialize the Reporter with the given API URL.
        """
        self._api = api_url

    def _request(self, method: str, suffix: str, *args, **kwargs) -> Optional[Dict]:
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

        kwargs["headers"].update({"User-Agent": "Train job"})

        url = urljoin(self._api, suffix)
        try:
            response = requests.request(method, url, *args, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as exception:
            print(exception)
            raise exception

    def report_complete(self, model_id: str, metadata: Dict[str, str]):
        """
        Report the completion of a training job.
        Args:
            model_id (str): The ID of the model.
            metadata (Dict[str, str]): Metadata associated with the training job.
        """
        json_data = {
            "model_id": model_id,
            "metadata": metadata,
        }
        content = self._request("post", "api/train/complete", json=json_data)
        print(content)

    def report_status(self, model_id: str, status: str, message: str = ""):
        """
        Report the status of a training job.
        Args:
            model_id (str): The ID of the model.
            status (str): The status of the training job.
            message (str, optional): Additional message. Defaults to "".
        """
        content = self._request(
            "post",
            "api/train/update-status",
            params={"model_id": model_id, "status": status, "message": message},
        )
        print(content)
