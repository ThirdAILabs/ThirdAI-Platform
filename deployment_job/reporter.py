import json
from typing import Dict
from urllib.parse import urljoin

import requests


class Reporter:
    def __init__(self, api_url: str):
        """
        Initializes the Reporter instance with the API URL.

        Args:
            api_url (str): The base URL for the API.
        """
        self._api = api_url

    def _request(self, method: str, suffix: str, *args, **kwargs) -> dict:
        """
        Makes an HTTP request to the specified API endpoint.

        Args:
            method (str): The HTTP method to use ('post' or 'get').
            suffix (str): The API endpoint suffix.
            *args: Additional positional arguments for the request.
            **kwargs: Additional keyword arguments for the request.

        Returns:
            dict: The JSON response content.

        Raises:
            requests.exceptions.HTTPError: If the request fails with an HTTP error.
            Exception: For other types of exceptions.
        """
        # The following exists to have custom user-agent so ngrok doesn't
        # provide an abuse page.
        if "headers" not in kwargs:
            kwargs["headers"] = {}

        kwargs["headers"].update({"User-Agent": "NDB Deployment job"})

        url = urljoin(self._api, suffix)
        try:
            if method == "post":
                response = requests.post(url, *args, **kwargs)
            elif method == "get":
                response = requests.get(url, *args, **kwargs)
            if 200 <= response.status_code < 300:
                content = json.loads(response.content)
                return content
            else:
                print(response.content)
                raise requests.exceptions.HTTPError(
                    "Failed with status code:", response.status_code
                )

        except Exception as exception:
            # This could be other forms of error like connection error, stuff not found.
            # In this case, we log the response from the server, but ignore the error.
            print(exception)
            raise exception

    def save_model(
        self,
        access_token: str,
        deployment_id: str,
        model_id: str,
        base_model_id: str,
        model_name: str,
        metadata: dict,
    ) -> None:
        """
        Saves the deployed model information.

        Args:
            access_token (str): The access token for authentication.
            deployment_id (str): The ID of the deployment.
            model_id (str): The ID of the model.
            base_model_id (str): The ID of the base model.
            model_name (str): The name of the model.
            metadata (dict): Metadata associated with the model.
        """
        content = self._request(
            "post",
            "api/model/save-deployed",
            json={
                "deployment_id": deployment_id,
                "model_id": model_id,
                "base_model_id": base_model_id,
                "model_name": model_name,
                "metadata": metadata,
            },
            headers=self.auth_header(access_token=access_token),
        )
        print(content)

    def auth_header(self, access_token: str) -> dict:
        """
        Generates the authentication header.

        Args:
            access_token (str): The access token for authentication.

        Returns:
            dict: The authentication header.
        """
        return {
            "Authorization": f"Bearer {access_token}",
        }

    def check_model_present(self, access_token: str, model_name: str) -> bool:
        """
        Checks if a model with the given name is already present.

        Args:
            access_token (str): The access token for authentication.
            model_name (str): The name of the model to check.

        Returns:
            bool: True if the model is present, False otherwise.
        """
        content = self._request(
            "get",
            "api/model/name-check",
            params={
                "name": model_name,
            },
            headers=self.auth_header(access_token=access_token),
        )
        print(content)

        return content["data"]["model_present"]

    def update_deploy_status(self, deployment_id: str, status: str) -> None:
        """
        Updates the deployment status.

        Args:
            deployment_id (str): The ID of the deployment.
            status (str): The new status of the deployment.
        """
        content = self._request(
            "post",
            "api/deploy/update-status",
            params={
                "deployment_id": deployment_id,
                "status": status,
            },
        )
        print(content)

    def log(
        self,
        action: str,
        deployment_id: str,
        train_samples: list,
        access_token: str,
        used: bool = False,
    ) -> None:
        """
        Logs an action for the deployment.

        Args:
            action (str): The action to log.
            deployment_id (str): The ID of the deployment.
            train_samples (list): The training samples associated with the action.
            access_token (str): The access token for authentication.
            used (bool): Whether the action was used. Defaults to False.
        """
        content = self._request(
            "post",
            "api/deploy/log",
            json={
                "deployment_id": deployment_id,
                "action": action,
                "train_samples": train_samples,
                "used": used,
            },
            headers=self.auth_header(access_token=access_token),
        )
        print(content)

    def pii_models(
        self,
        access_token: str,
    ):
        content = self._request(
            "post",
            "api/models/list",
            json={"name": "", "type": "udt", "sub_type": "token"},
            headers=self.auth_header(access_token=access_token),
        )
        print(content)

        return content["data"]

    def update_pii_metadata(
        self,
        deployment_id: str,
        metadata: Dict[str, str],
        access_token: str,
    ):
        content = self._request(
            "post",
            "api/deploy/update-metadata",
            json={"deployment": deployment_id, "metadata": metadata},
            headers=self.auth_header(access_token=access_token),
        )
        print(content)
