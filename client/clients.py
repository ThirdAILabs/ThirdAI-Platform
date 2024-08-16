from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

from requests.auth import HTTPBasicAuth

from .utils import (
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

        downvote(self, text_id_pairs: List[Dict[str, Union[str, int]]]) -> None:
            Downvotes a response in the ndb model.

        chat(self, user_input: str, session_id: str) -> Dict[str, str]:
            Returns a reply given the user_input and the chat history associated with session_id

        get_chat_history(self, session_id: str) -> Dict[List[Dict[str, str]]]:
            Returns chat history associated with session_id

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

        base_params = {"query": query, "top_k": top_k}

        ndb_params = {"constraints": constraints}

        response = http_post_with_error(
            urljoin(self.base_url, "predict"),
            json={"base_params": base_params, "ndb_params": ndb_params},
            headers=auth_header(self.login_instance.access_token),
        )

        return json.loads(response.content)["data"]

    @check_deployment_decorator
    def insert(self, documents: list[dict[str, Any]], input_mode="sync"):
        """
        Inserts documents into the ndb model.

        Args:
            documents (List[dict[str, Any]]): A list of dictionaries that represent documents to be inserted to the ndb model.
                The document dictionaries must be in the following format:
                {"document_type": "DOCUMENT_TYPE", **kwargs} where "DOCUMENT_TYPE" is one of the following:
                "PDF", "CSV", "DOCX", "URL", "SentenceLevelPDF", "SentenceLevelDOCX", "Unstructured", "InMemoryText".
                The kwargs for each document type are shown below:

                class PDF(Document):
                    document_type: Literal["PDF"]
                    path: str
                    metadata: Optional[dict[str, Any]] = None
                    on_disk: bool = False
                    version: str = "v1"
                    chunk_size: int = 100
                    stride: int = 40
                    emphasize_first_words: int = 0
                    ignore_header_footer: bool = True
                    ignore_nonstandard_orientation: bool = True

                class CSV(Document):
                    document_type: Literal["CSV"]
                    path: str
                    id_column: Optional[str] = None
                    strong_columns: Optional[List[str]] = None
                    weak_columns: Optional[List[str]] = None
                    reference_columns: Optional[List[str]] = None
                    save_extra_info: bool = True
                    metadata: Optional[dict[str, Any]] = None
                    has_offset: bool = False
                    on_disk: bool = False

                class DOCX(Document):
                    document_type: Literal["DOCX"]
                    path: str
                    metadata: Optional[dict[str, Any]] = None
                    on_disk: bool = False

                class URL(Document):
                    document_type: Literal["URL"]
                    url: str
                    save_extra_info: bool = True
                    title_is_strong: bool = False
                    metadata: Optional[dict[str, Any]] = None
                    on_disk: bool = False

                class SentenceLevelPDF(Document):
                    document_type: Literal["SentenceLevelPDF"]
                    path: str
                    metadata: Optional[dict[str, Any]] = None
                    on_disk: bool = False

                class SentenceLevelDOCX(Document):
                    document_type: Literal["SentenceLevelDOCX"]
                    path: str
                    metadata: Optional[dict[str, Any]] = None
                    on_disk: bool = False

                class Unstructured(Document):
                    document_type: Literal["Unstructured"]
                    path: str
                    save_extra_info: bool = True
                    metadata: Optional[dict[str, Any]] = None
                    on_disk: bool = False

                class InMemoryText(Document):
                    document_type: Literal["InMemoryText"]
                    name: str
                    texts: list[str]
                    metadatas: Optional[list[dict[str, Any]]] = None
                    global_metadata: Optional[dict[str, Any]] = None
                    on_disk: bool = False

                For Document types with the arg "path", ensure that the path exists on your local machine.
        """

        if not documents:
            raise ValueError("Documents cannot be empty.")

        files = []
        for doc in documents:
            if "path" in doc and ("location" not in doc or doc["location"] == "local"):
                if not os.path.exists(doc["path"]):
                    raise ValueError(
                        f"Path {doc['path']} was provided but doesn't exist on the machine."
                    )
                files.append(("files", open(doc["path"], "rb")))

        files.append(("documents", (None, json.dumps(documents), "application/json")))
        files.append(("input_mode", (None, input_mode)))

        response = http_post_with_error(
            urljoin(self.base_url, "insert"),
            files=files,
            headers=auth_header(self.login_instance.access_token),
        )

        return json.loads(response.content)["data"]

    @check_deployment_decorator
    def task_status(self, task_id: str):
        """
        Gets the task for the given task_id

        Args:
            task_id (str): A task id

        """

        response = http_post_with_error(
            urljoin(self.base_url, "task-status"),
            params={"task_id": task_id},
            headers=auth_header(self.login_instance.access_token),
        )

        return json.loads(response.content)["data"]

    @check_deployment_decorator
    def delete(self, source_ids: List[str]):
        """
        Deletes documents from the ndb model using source ids.

        Args:
            files (List[str]): A list of source ids to delete from the ndb model.
        """
        response = http_post_with_error(
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
        response = http_post_with_error(
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
        response = http_post_with_error(
            urljoin(self.base_url, "upvote"),
            json={"text_id_pairs": text_id_pairs},
            headers=auth_header(self.login_instance.access_token),
        )

        print("Successfully upvoted the specified search result.")

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
    def search(self, query, top_k=1):
        """
        Queries the UDT Model

        Args:
            query (str): The query to search for.
            top_k (int): The number of top results to retrieve (default is 5).
        """
        print(self.base_url)

        base_params = {"query": query, "top_k": top_k}

        response = http_post_with_error(
            urljoin(self.base_url, "predict"),
            json=base_params,
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
