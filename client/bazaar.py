import json
import os
import time
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin

from client.clients import BaseClient, Login, Model, NeuralDBClient, UDTClient
from client.utils import (
    auth_header,
    create_model_identifier,
    download_files_from_s3,
    http_delete_with_error,
    http_get_with_error,
    http_post_with_error,
    print_progress_dots,
)


class ModelBazaar:
    def __init__(
        self,
        base_url: str,
        cache_dir: Union[Path, str] = "./bazaar_cache",
    ):
        cache_dir = Path(cache_dir)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        self._cache_dir = cache_dir
        if not base_url.endswith("/api/"):
            raise ValueError("base_url must end with '/api/'.")
        self._base_url = base_url
        self._login_instance = Login(base_url=base_url)
        self._username = None
        self._access_token = None
        self._doc_types = ["local", "nfs", "s3"]

    def sign_up(self, email, password, username):
        json_data = {
            "username": username,
            "email": email,
            "password": password,
        }

        response = http_post_with_error(
            urljoin(self._base_url, "user/email-signup-basic"),
            json=json_data,
        )
        self._username = username

        print(
            f"Successfully signed up. Please check your email ({email}) to verify your account."
        )

    def log_in(self, email, password):
        self._login_instance = Login.with_email(self._base_url, email, password)
        self._access_token = self._login_instance.access_token
        self._username = self._login_instance.username

    def add_global_admin(self, email):
        response = http_post_with_error(
            urljoin(self._base_url, "user/add-global-admin"),
            json={"email": email},
            headers=auth_header(self._login_instance.access_token),
        )
        return response

    def delete_user(self, email):
        response = http_delete_with_error(
            urljoin(self._base_url, "user/delete-user"),
            json={"email": email},
            headers=auth_header(self._login_instance.access_token),
        )
        return response

    def add_secret_key(self, key, value):
        secret_data = {"key": key, "value": value}

        response = http_post_with_error(
            urljoin(self._base_url, "vault/add-secret"),
            json=secret_data,
            headers=auth_header(self._login_instance.access_token),
        )
        return response

    def get_secret_key(self, key):
        secret_data = {"key": key}

        response = http_get_with_error(
            urljoin(self._base_url, "vault/get-secret"),
            json=secret_data,
            headers=auth_header(self._login_instance.access_token),
        )

        return response

    def create_team(self, name):
        response = http_post_with_error(
            urljoin(self._base_url, "team/create-team"),
            params={"name": name},
            headers=auth_header(self._login_instance.access_token),
        )
        response_content = json.loads(response.content)
        return response_content["data"]["team_id"]

    def remove_user_from_team(self, user_email, team_id):
        response = http_post_with_error(
            urljoin(self._base_url, "team/remove-user-from-team"),
            params={"email": user_email, "team_id": team_id},
            headers=auth_header(self._login_instance.access_token),
        )
        return response

    def add_user_to_team(self, user_email, team_id):
        response = http_post_with_error(
            urljoin(self._base_url, "team/add-user-to-team"),
            params={"email": user_email, "team_id": team_id},
            headers=auth_header(self._login_instance.access_token),
        )
        return response

    def assign_team_admin(self, user_email, team_id):
        response = http_post_with_error(
            urljoin(self._base_url, "team/assign-team-admin"),
            params={"email": user_email, "team_id": team_id},
            headers=auth_header(self._login_instance.access_token),
        )
        return response

    def delete_team(self, team_id):
        response = http_delete_with_error(
            urljoin(self._base_url, "team/delete-team"),
            params={"team_id": team_id},
            headers=auth_header(self._login_instance.access_token),
        )
        return response

    def is_logged_in(self):
        return self._login_instance.username is not None

    def train(
        self,
        model_name: str,
        unsupervised_docs: Optional[List[str]] = None,
        supervised_docs: Optional[List[Tuple[str, str]]] = None,
        test_doc: Optional[str] = None,
        doc_type: str = "local",
        sharded: bool = False,
        is_async: bool = False,
        base_model_identifier: Optional[str] = None,
        train_extra_options: Optional[dict] = None,
        metadata: Optional[List[Dict[str, str]]] = None,
    ):
        """
        Initiates training for a model and returns a Model instance.

        Args:
            model_name (str): The name of the model.
            unsupervised_docs (Optional[List[str]]): A list of document paths for unsupervised training.
            supervised_docs (Optional[List[Tuple[str, str]]]): A list of document path and source id pairs.
            test_doc (Optional[str]): A path to a test file for evaluating the trained NeuralDB.
            doc_type (str): Specifies document location type : "local"(default), "nfs" or "s3".
            sharded (bool): Whether NeuralDB training will be distributed over NeuralDB shards.
            is_async (bool): Whether training should be asynchronous (default is False).
            train_extra_options: (Optional[dict])
            base_model_identifier (Optional[str]): The identifier of the base model.
            metadata (Optional[List[Dict[str, str]]]): A list metadata dicts. Each dict corresponds to an unsupervised file.

        Returns:
            Model: A Model instance.
        """
        if doc_type not in self._doc_types:
            raise ValueError(
                f"Invalid doc_type value. Supported doc_type are {self._doc_types}"
            )

        if not unsupervised_docs and not supervised_docs:
            raise ValueError("Both the unsupervised and supervised docs are empty.")

        if metadata and unsupervised_docs:
            if len(metadata) != len(unsupervised_docs):
                raise ValueError("Metadata is not provided for all unsupervised files.")

        file_details_list = []
        docs = []

        if unsupervised_docs and metadata:
            for doc, meta in zip(unsupervised_docs, metadata):
                docs.append(doc)
                file_details_list.append(
                    {"mode": "unsupervised", "location": doc_type, "metadata": meta}
                )
        elif unsupervised_docs:
            for doc in unsupervised_docs:
                docs.append(doc)
                file_details_list.append({"mode": "unsupervised", "location": doc_type})

        if supervised_docs:
            for sup_file, source_id in supervised_docs:
                docs.append(sup_file)
                file_details_list.append(
                    {"mode": "supervised", "location": doc_type, "source_id": source_id}
                )

        if test_doc:
            docs.append(test_doc)
            file_details_list.append({"mode": "test", "location": doc_type})

        url = urljoin(self._base_url, f"train/ndb")
        files = [
            (
                ("files", open(file_path, "rb"))
                if doc_type == "local"
                else ("files", (file_path, "don't care"))
            )
            for file_path in docs
        ]
        if train_extra_options:
            files.append(
                (
                    "extra_options_form",
                    (None, json.dumps(train_extra_options), "application/json"),
                )
            )

        files.append(
            (
                "file_details_list",
                (
                    None,
                    json.dumps({"file_details": file_details_list}),
                    "application/json",
                ),
            )
        )

        response = http_post_with_error(
            url,
            params={
                "model_name": model_name,
                "base_model_identifier": base_model_identifier,
            },
            files=files,
            headers=auth_header(self._access_token),
        )
        print(response.content)
        response_content = json.loads(response.content)
        if response_content["status"] != "success":
            raise Exception(response_content["message"])

        model = Model(
            model_identifier=create_model_identifier(
                model_name=model_name, author_username=self._username
            ),
            model_id=response_content["data"]["model_id"],
        )

        if is_async:
            return model

        self.await_train(model)
        return model

    def train_udt(
        self,
        model_name: str,
        supervised_docs: List[str],
        test_doc: Optional[str] = None,
        doc_type: str = "local",
        is_async: bool = False,
        base_model_identifier: Optional[str] = None,
        train_extra_options: Optional[dict] = None,
    ):
        """
        Initiates training for a model and returns a Model instance.

        Args:
            model_name (str): The name of the model.
            docs (Optional[List[str]]): A list of document paths for supervised training.
            test_doc (Optional[str]): A path to a test file for evaluating the trained udt model.
            doc_type (str): Specifies document location type : "local"(default), "nfs" or "s3".
            is_async (bool): Whether training should be asynchronous (default is False).
            train_extra_options: (Optional[dict])
            base_model_identifier (Optional[str]): The identifier of the base model.
            metadata (Optional[List[Dict[str, str]]]): A list metadata dicts. Each dict corresponds to an unsupervised file.

        Returns:
            Model: A Model instance.
        """
        if doc_type not in self._doc_types:
            raise ValueError(
                f"Invalid doc_type value. Supported doc_type are {self._doc_types}"
            )

        if not supervised_docs:
            raise ValueError("supervised docs are empty.")

        file_details_list = []
        docs = []
        for doc in supervised_docs:
            docs.append(doc)
            file_details_list.append({"mode": "supervised", "location": doc_type})

        if test_doc:
            docs.append(test_doc)
            file_details_list.append({"mode": "test", "location": doc_type})

        url = urljoin(self._base_url, f"train/udt")
        files = [
            (
                ("files", open(file_path, "rb"))
                if doc_type == "local"
                else ("files", (file_path, "don't care"))
            )
            for file_path in docs
        ]
        if train_extra_options:
            files.append(
                (
                    "extra_options_form",
                    (None, json.dumps(train_extra_options), "application/json"),
                )
            )

        files.append(
            (
                "file_details_list",
                (
                    None,
                    json.dumps({"file_details": file_details_list}),
                    "application/json",
                ),
            )
        )

        response = http_post_with_error(
            url,
            params={
                "model_name": model_name,
                "base_model_identifier": base_model_identifier,
            },
            files=files,
            headers=auth_header(self._access_token),
        )
        print(response.content)
        response_content = json.loads(response.content)
        if response_content["status"] != "success":
            raise Exception(response_content["message"])

        model = Model(
            model_identifier=create_model_identifier(
                model_name=model_name, author_username=self._username
            ),
            model_id=response_content["data"]["model_id"],
        )

        if is_async:
            return model

        self.await_train(model)
        return model

    def train_udt_with_datagen(
        self,
        model_name: str,
        task_prompt: str,
        sub_type: str,
        examples: List[Tuple[str, str, str]],
        is_async: bool = False,
        base_model_identifier: Optional[str] = None,
        train_extra_options: Optional[dict] = None,
    ):
        """
        Initiates training for a model with datagen and returns a Model instance.

        Args:
            model_name (str): The name of the model.
            examples (List[Tuple[str, str, str]]): A list of examples for training as (category, example, description) triplets.
            is_async (bool): Whether training should be asynchronous (default is False).
            base_model_identifier (Optional[str]): The identifier of the base model.
            train_extra_options (Dict[str, Any]): Extra options for training.

        Returns:
            Model: A Model instance.
        """
        url = urljoin(self._base_url, f"train/udt")
        form = []
        
        train_extra_options = train_extra_options or {}
        train_extra_options["target_labels"] = list(set([category for category, _, _ in examples]))
        form.append(
            (
                "extra_options_form",
                (None, json.dumps(train_extra_options), "application/json"),
            )
        )

        category_examples = {}
        category_descriptions = {}
        for category, example, description in examples:
            if category not in category_examples:
                category_examples[category] = [example]
                category_descriptions[category] = description
            else:
                category_examples[category].append(example)
        
        if sub_type == "text":
            datagen_options = {
                "samples_per_label": max(math.ceil(10_000 / len(category_examples)), 50),
                "target_labels": list(category_examples.keys()),
                "examples": category_examples,
                "labels_description": category_descriptions,
            }
        else:
            datagen_options = {
                "domain_prompt": task_prompt,
                "tags": list(category_examples.keys()),
                "tag_examples": category_examples,
                "num_sentences_to_generate": 10_000,
                "num_samples_per_tag": max(math.ceil(10_000 / len(category_examples)), 50),
            }
        form.append(
            (
                "datagen_options_form",
                (None, json.dumps(datagen_options), "application/json"),
            )
        )

        response = http_post_with_error(
            url,
            params={
                "model_name": model_name,
                "task_prompt": task_prompt,
                "base_model_identifier": base_model_identifier,
            },
            files=form,
            headers=auth_header(self._access_token),
        )
        print(response.content)
        response_content = json.loads(response.content)
        if response_content["status"] != "success":
            raise Exception(response_content["message"])

        model = Model(
            model_identifier=create_model_identifier(
                model_name=model_name, author_username=self._username
            ),
            model_id=response_content["data"]["model_id"],
        )

        if is_async:
            return model

        self.await_train(model)
        return model


    def train_status(self, model: Model):
        """
        Checks for the status of the model training

        Args:
            model (Model): The Model instance.
        """

        url = urljoin(self._base_url, f"train/status")

        response = http_get_with_error(
            url,
            params={"model_identifier": model.model_identifier},
            headers=auth_header(self._access_token),
        )

        response_data = json.loads(response.content)["data"]

        return response_data

    def await_train(self, model: Model):
        """
        Waits for the training of a model to complete.

        Args:
            model (Model): The Model instance.
        """
        while True:
            response_data = self.train_status(model)

            if response_data["train_status"] == "complete":
                print("\nTraining completed")
                return

            if response_data["train_status"] == "failed":
                print("\nTraining Failed")
                raise ValueError(f"Training Failed for {model.model_identifier}")

            print("Training: In progress", end="", flush=True)
            print_progress_dots(duration=10)

    def deploy(
        self,
        model_identifier: str,
        memory: Optional[int] = None,
        is_async=False,
    ):
        """
        Deploys a model and returns a NeuralDBClient instance.

        Args:
            model_identifier (str): The identifier of the model.
            deployment_name (str): The name for the deployment.
            is_async (bool): Whether deployment should be asynchronous (default is False).

        Returns:
            NeuralDBClient: A NeuralDBClient instance.
        """
        url = urljoin(self._base_url, f"deploy/run")
        params = {
            "model_identifier": model_identifier,
            "memory": memory,
        }
        response = http_post_with_error(
            url, params=params, headers=auth_header(self._access_token)
        )
        response_data = json.loads(response.content)["data"]

        ndb_client = NeuralDBClient(
            model_identifier=model_identifier,
            model_id=response_data["model_id"],
            login_instance=self._login_instance,
        )
        if is_async:
            return ndb_client

        time.sleep(5)
        self.await_deploy(ndb_client)
        return ndb_client

    def deploy_udt(
        self,
        model_identifier: str,
        deployment_name: str,
        memory: Optional[int] = None,
        is_async=False,
    ):
        url = urljoin(self._base_url, f"deploy/run")
        params = {
            "model_identifier": model_identifier,
            "memory": memory,
        }
        response = http_post_with_error(
            url, params=params, headers=auth_header(self._access_token)
        )
        response_data = json.loads(response.content)["data"]

        udt_client = UDTClient(
            model_identifier=model_identifier,
            model_id=response_data["model_id"],
            login_instance=self._login_instance,
        )
        if is_async:
            return udt_client

        time.sleep(5)
        self.await_deploy(udt_client)
        return udt_client

    def await_deploy(self, ndb_client: BaseClient):
        """
        Waits for the deployment of a model to complete.

        Args:
            ndb_client (NeuralDBClient): The NeuralDBClient instance.
        """
        url = urljoin(self._base_url, f"deploy/status")

        params = {"model_identifier": ndb_client.model_identifier}
        while True:
            response = http_get_with_error(
                url, params=params, headers=auth_header(self._access_token)
            )
            response_data = json.loads(response.content)["data"]

            if response_data["deploy_status"] == "complete":
                print("\nDeployment completed")
                return

            print("Deployment: In progress", end="", flush=True)
            print_progress_dots(duration=5)

    def undeploy(self, ndb_client: BaseClient):
        """
        Undeploys a deployed model.

        Args:
            ndb_client (NeuralDBClient): The NeuralDBClient instance.
        """
        url = urljoin(self._base_url, f"deploy/stop")
        params = {
            "model_identifier": ndb_client.model_identifier,
        }
        response = http_post_with_error(
            url, params=params, headers=auth_header(self._access_token)
        )

        print("Deployment is shutting down.")

    # TODO(pratik): add a unit tests for this function
    @staticmethod
    def full_backup_restore(bucket_name, local_dir, database_uri):
        import boto3

        os.environ["DATABASE_URI"] = database_uri
        os.environ["SHARE_DIR"] = local_dir

        download_files_from_s3(bucket_name, local_dir)

        print("Backup and restore operations completed successfully.")
