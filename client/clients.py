from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth

from client.utils import (
    auth_header,
    check_deployment_decorator,
    construct_deployment_url,
    create_model_identifier,
    http_get_with_error,
    http_post_with_error,
)


class Model:
    """
    A class representing a model listed on NeuralDB Enterprise.

    Attributes:
        _model_identifier (str): The unique identifier for the model.

    Methods:
        __init__(self, model_identifier: str) -> None:
            Initializes a new instance of the Model class.

            Parameters:
                model_identifier (str): An optional model identifier.

        model_identifier(self) -> str:
            Getter method for accessing the model identifier.

            Returns:
                str: The model identifier, or None if not set.
    """

    def __init__(self, model_identifier, model_id=None) -> None:
        self._model_identifier = model_identifier
        self._model_id = model_id

    @property
    def model_identifier(self):
        return self._model_identifier

    @property
    def model_id(self):
        if self._model_id:
            return self._model_id
        raise ValueError("Model id is not yet set.")


import json
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

from requests.auth import HTTPBasicAuth


@dataclass
class Login:
    base_url: Optional[str] = None
    username: Optional[str] = None
    access_token: Optional[str] = None

    @staticmethod
    def with_email(base_url: str, email: str, password: str) -> "Login":
        # We are using HTTPBasic Auth in backend. update this when we change the Authentication in Backend.
        response = http_get_with_error(
            urljoin(base_url, "user/email-login"),
            auth=HTTPBasicAuth(email, password),
        )

        content = json.loads(response.content)
        username = content["data"]["user"]["username"]
        access_token = content["data"]["access_token"]
        return Login(base_url, username, access_token)


class BaseClient:
    """
    A base client for interacting with deployed models.

    Attributes:
        model_identifier (str): The identifier for the deployment.
        model_id (str): The deployment ID for the deployed model.
        login_instance (Login): Login instance for the current user.
    """

    def __init__(self, model_identifier: str, model_id: str, login_instance: Login):
        """
        Initializes a new instance of the BaseClient.

        Args:
            model_identifier (str): The identifier for the deployment.
            model_id (str): The deployment ID for the deployed model.
            Login instance for the current user. (Login): Login instance for the current user.
        """
        self.model_identifier = model_identifier
        self.model_id = model_id
        self.login_instance = login_instance
        self.base_url = construct_deployment_url(
            re.sub(r"api/$", "", login_instance.base_url), model_id
        )


class NeuralDBClient(BaseClient):
    """
    A client for interacting with the deployed NeuralDB model.

    Attributes:
        model_identifier (str): The identifier for the deployment.
        model_id (str): The deployment ID for the deployed NeuralDB model.
        bazaar (thirdai.neural_db.ModelBazaar): The bazaar object corresponding to a NeuralDB Enterprise installation

    Methods:
        __init__(self, model_identifier: str, model_id: str, bazaar: ModelBazaar) -> None:
            Initializes a new instance of the NeuralDBClient.

        search(self, query, top_k=5, constraints: Optional[dict[str, dict[str, str]]]=None) -> List[dict]:
            Searches the ndb model for relevant search results.

        insert(self, documents: list[dict[str, Any]]) -> None:
            Inserts documents into the ndb model.

        delete(self, source_ids: List[str]) -> None:
            Deletes documents from the ndb model

        associate(self, text_pairs (List[Dict[str, str]])) -> None:
            Associates source and target string pairs in the ndb model.

        upvote(self, text_id_pairs: List[Dict[str, Union[str, int]]]) -> None:
            Upvotes a response in the ndb model.

        sources(self) -> List[Dict[str, str]]:
            Gets the source names and ids of documents in the ndb model
    """

    def __init__(self, model_identifier: str, model_id: str, login_instance: Login):
        """
        Initializes a new instance of the NeuralDBClient.

        Args:
            model_identifier (str): The identifier for the deployment.
            model_id (str): The deployment ID for the deployed NeuralDB model.
            login_instance (Login): Login Instance for the current user
        """
        super().__init__(
            model_identifier=model_identifier,
            model_id=model_id,
            login_instance=login_instance,
        )

    @check_deployment_decorator
    def search(
        self, query, top_k=5, constraints: Optional[dict[str, dict[str, str]]] = {}
    ):
        """
        Searches the ndb model for similar queries.

        Args:
            query (str): The query to search for.
            top_k (int): The number of top results to retrieve (default is 10).
            constraints (Optional[dict[str, dict[str, str]]]): Constraints to filter the search result metadata by.
                These constraints must be in the following format:
                {"FIELD_NAME": {"constraint_type": "CONSTRAINT_NAME", **kwargs}} where
                "FIELD_NAME" is the field that you want to filter over, and "CONSTRAINT_NAME"
                is one of the following: "AnyOf", "EqualTo", "InRange", "GreaterThan", and "LessThan".
                The kwargs for the above constraints are shown below:

                class AnyOf(BaseModel):
                    constraint_type: Literal["AnyOf"]
                    values: Iterable[Any]

                class EqualTo(BaseModel):
                    constraint_type: Literal["EqualTo"]
                    value: Any

                class InRange(BaseModel):
                    constraint_type: Literal["InRange"]
                    minimum: Any
                    maximum: Any
                    inclusive_min: bool = True
                    inclusive_max: bool = True

                class GreaterThan(BaseModel):
                    constraint_type: Literal["GreaterThan"]
                    minimum: Any
                    include_equal: bool = False

                class LessThan(BaseModel):
                    constraint_type: Literal["LessThan"]
                    maximum: Any
                    include_equal: bool = False

        Returns:
            Dict: A dict of search results containing keys: `query_text` and `references`.
        """
        print(self.base_url)

        response = http_post_with_error(
            urljoin(self.base_url, "predict"),
            json={"query": query, "top_k": top_k, "constraints": constraints},
            headers=auth_header(self.login_instance.access_token),
        )

        return json.loads(response.content)["data"]

    @check_deployment_decorator
    def insert(self, documents: list[dict[str, Any]]):
        """
        Inserts documents into the ndb model.

        Args:
            documents (List[dict[str, Any]]): A list of dictionaries that represent documents to be inserted to the ndb model.
                The document dictionaries can have the following fields:
                - path (str): the path to the document (either local or s3 bucket).
                - location (str): where the file is found either "local" or "s3".
                  Optional, defaults to "local".
                - doc_id (Optional[str]): an optional arg to indicate the id to use to
                  reference the document. Optional.
                - metadata (Dict[str, Any]): metadata for the document. Optional.
                - options (Dict[str, Any]): any options for specific document types. Optional.
        """

        if not documents:
            raise ValueError("Documents cannot be empty.")

        files = []
        for doc in documents:
            if "location" not in doc:
                doc["location"] = "local"
            if doc["location"] == "local":
                if not os.path.exists(doc["path"]):
                    raise ValueError(
                        f"Path {doc['path']} was provided but doesn't exist on the machine."
                    )
                files.append(("files", open(doc["path"], "rb")))

        files.append(
            (
                "documents",
                (None, json.dumps({"documents": documents}), "application/json"),
            )
        )

        http_post_with_error(
            urljoin(self.base_url, "insert"),
            files=files,
            headers=auth_header(self.login_instance.access_token),
        )

    @check_deployment_decorator
    def delete(self, source_ids: List[str]):
        """
        Deletes documents from the ndb model using source ids.

        Args:
            files (List[str]): A list of source ids to delete from the ndb model.
        """
        http_post_with_error(
            urljoin(self.base_url, "delete"),
            json={"source_ids": source_ids},
            headers=auth_header(self.login_instance.access_token),
        )

    @check_deployment_decorator
    def associate(self, text_pairs: List[Dict[str, str]]):
        """
        Associates source and target string pairs in the ndb model.

        Args:
            text_pairs (List[Dict[str, str]]): List of dictionaries where each dictionary has 'source' and 'target' keys.
        """
        http_post_with_error(
            urljoin(self.base_url, "associate"),
            json={"text_pairs": text_pairs},
            headers=auth_header(self.login_instance.access_token),
        )

    @check_deployment_decorator
    def save_model(self, override: bool = True, model_name: Optional[str] = None):
        response = http_post_with_error(
            urljoin(self.base_url, "save"),
            json={"override": override, "model_name": model_name},
            headers=auth_header(self.login_instance.access_token),
        )

        print("Successfully saved the model.")

        content = response.json()["data"]

        if content["new_model_id"]:
            return Model(
                model_identifier=create_model_identifier(
                    model_name, self.login_instance.username
                ),
                model_id=content["new_model_id"],
            )

        return None

    @check_deployment_decorator
    def upvote(self, text_id_pairs: List[Dict[str, Union[str, int]]]):
        """
        Upvote response with 'reference_id' corresponding to 'query_text' in the ndb model.

        Args:
            text_id_pairs: (List[Dict[str, Union[str, int]]]): List of dictionaries where each dictionary has 'query_text' and 'reference_id' keys.
        """
        http_post_with_error(
            urljoin(self.base_url, "upvote"),
            json={"text_id_pairs": text_id_pairs},
            headers=auth_header(self.login_instance.access_token),
        )

    @check_deployment_decorator
    def sources(self) -> List[Dict[str, str]]:
        """
        Gets the source names and ids of documents in the ndb model

        """
        response = http_get_with_error(
            urljoin(self.base_url, "sources"),
            headers=auth_header(self.login_instance.access_token),
        )

        return response.json()["data"]

    @check_deployment_decorator
    def llm_client(self) -> LLMClient:
        return LLMClient(self.login_instance, self)


class LLMClient:
    def __init__(self, login_instance: Login, neuraldb_client: NeuralDBClient):
        self.login_instance = login_instance
        self.base_url = re.sub(r"api/$", "", login_instance.base_url)
        self.neuraldb_client = neuraldb_client

    def generate(
        self,
        query: str,
        api_key: str,
        provider: str = "openai",
        use_cache: bool = False,
    ):
        cache_result = None

        # Check cache if use_cache is enabled
        if use_cache:
            # Query cache for the result
            cache_response = http_get_with_error(
                urljoin(self.base_url, "cache/query"),
                headers=auth_header(self.login_instance.access_token),
                params={"model_id": self.neuraldb_client.model_id, "query": query},
            )

            cache_result = json.loads(cache_response.content).get("cached_response")

        if cache_result:
            return cache_result

        # No cached result or cache disabled, proceed with generation
        token_response = http_get_with_error(
            urljoin(self.base_url, "cache/token"),
            headers=auth_header(self.login_instance.access_token),
            params={"model_id": self.neuraldb_client.model_id},
        )

        cache_token = json.loads(token_response.content)["access_token"]

        response = requests.post(
            urljoin(self.base_url, "llm-dispatch/generate"),
            headers={
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "key": api_key,
                "provider": provider,
                "original_query": query,
                "cache_access_token": cache_token,
            },
        )

        print(response.content)

        if response.status_code != 200:
            print("Network response was not ok")
            raise

        return response.text


class UDTClient(BaseClient):
    """
    A client for interacting with deployed UDT Model

    Attributes:
        model_identifier (str): The identifier for the deployment.
        model_id (str): The deployment ID for the deployed UDT model.
        login_instance (Login): Login Instance for the current user.

    """

    def __init__(self, model_identifier: str, model_id: str, login_instance: Login):
        """
        Initializes a new instance of the UDTClient.

        Args:
            model_identifier (str): The identifier for the deployment.
            model_id (str): The deployment ID for the deployed UDT model.
            bazaar (thirdai.neural_db.ModelBazaar): Login Instance for the current user.
        """

        super().__init__(
            model_identifier=model_identifier,
            model_id=model_id,
            login_instance=login_instance,
        )

    @check_deployment_decorator
    def predict(self, text, top_k=1):
        """
        Queries the UDT Model

        Args:
            query (str): The query to search for.
            top_k (int): The number of top results to retrieve (default is 5).
        """
        print(self.base_url)

        response = http_post_with_error(
            urljoin(self.base_url, "predict"),
            json={"text": text, "top_k": top_k},
            headers=auth_header(self.login_instance.access_token),
        )

        return json.loads(response.content)["data"]


class WorkflowClient(BaseClient):
    def __init__(self, login_instance: Login):
        super().__init__(
            model_identifier=None,
            model_id=None,
            login_instance=login_instance,
        )

    def create_workflow(self, name: str, type: str):
        url = urljoin(self.login_instance.base_url, "workflow/create")
        response = http_post_with_error(
            url,
            params={
                "name": name,
                "type_name": type,
            },
            headers=auth_header(self.login_instance.access_token),
        )

        response_content = json.loads(response.content)
        return response_content["data"]["workflow_id"]

    def add_models(self, workflow_id: str, model_ids: List[str], components: List[str]):
        url = urljoin(self.login_instance.base_url, "workflow/add-models")
        response = http_post_with_error(
            url,
            json={
                "workflow_id": workflow_id,
                "model_ids": model_ids,
                "components": components,
            },
            headers=auth_header(self.login_instance.access_token),
        )
        response_content = json.loads(response.content)
        return response_content["data"]["models"]

    def delete_models(
        self, workflow_id: str, model_ids: List[str], components: List[str]
    ):
        url = urljoin(self.login_instance.base_url, "workflow/delete-models")
        response = http_post_with_error(
            url,
            params={
                "workflow_id": workflow_id,
                "model_ids": model_ids,
                "components": components,
            },
            headers=auth_header(self.login_instance.access_token),
        )
        response_content = json.loads(response.content)
        return response_content["data"]["models"]

    def validate_workflow(self, workflow_id: str):
        url = urljoin(self.login_instance.base_url, "workflow/validate")
        response = http_post_with_error(
            url,
            params={"workflow_id": workflow_id},
            headers=auth_header(self.login_instance.access_token),
        )

    def stop_workflow(self, workflow_id: str):
        url = urljoin(self.login_instance.base_url, "workflow/stop")
        response = http_post_with_error(
            url,
            params={"workflow_id": workflow_id},
            headers=auth_header(self.login_instance.access_token),
        )

    def start_workflow(self, workflow_id: str):
        url = urljoin(self.login_instance.base_url, "workflow/start")
        response = http_post_with_error(
            url,
            params={"workflow_id": workflow_id},
            headers=auth_header(self.login_instance.access_token),
        )

    def delete_workflow(self, workflow_id: str):
        url = urljoin(self.login_instance.base_url, "workflow/delete")
        response = http_post_with_error(
            url,
            params={"workflow_id": workflow_id},
            headers=auth_header(self.login_instance.access_token),
        )
