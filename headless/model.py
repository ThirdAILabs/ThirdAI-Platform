import os
from typing import Dict, List, Optional, Tuple

from thirdai.neural_db import ModelBazaar

from headless.utils import get_csv_source_id


class Flow:
    def __init__(self, base_url: str, email: str, password: str):
        """
        Initializes the Flow object and logs into the ModelBazaar.

        Parameters:
        base_url (str): Base URL of the ModelBazaar API.
        email (str): Email for authentication.
        password (str): Password for authentication.
        """
        self._bazaar_client = ModelBazaar(base_url=base_url)
        self._bazaar_client.log_in(email=email, password=password)

    @property
    def bazaar_client(self) -> ModelBazaar:
        """
        Returns the ModelBazaar client.

        Returns:
        ModelBazaar: The ModelBazaar client.
        """
        return self._bazaar_client

    def train(
        self,
        model_name: str,
        unsupervised_docs: Optional[List[str]] = None,
        supervised_docs: Optional[List[Tuple[str, str]]] = None,
        test_doc: Optional[str] = None,
        doc_type: str = "local",
        extra_options: Optional[Dict[str, str]] = {},
        base_model_identifier: Optional[str] = None,
        is_async: bool = True,
        metadata: Optional[List[Dict[str, str]]] = None,
        nfs_base_path: Optional[str] = None,
    ):
        """
        Trains a model with the given documents and options.

        Parameters:
        model_name (str): Name of the model.
        unsupervised_docs (list[str], optional): List of paths to unsupervised documents.
        supervised_docs (list[tuple[str, str]], optional): List of tuples containing paths to supervised and unsupervised documents.
        test_doc (str, optional): Path to the test document.
        doc_type (str, optional): Type of documents (e.g., local, nfs).
        extra_options (dict, optional): Additional training options.
        base_model_identifier (str, optional): Identifier for the base model.
        is_async (bool, optional): Whether the training should be asynchronous.
        metadata (list[dict[str, str]], optional): Metadata for the documents.
        nfs_base_path (str, optional): Base path for NFS storage.
        """

        print("*" * 50 + f" Training the model: {model_name} " + "*" * 50)
        if supervised_docs:
            if metadata is None:
                metadata = [None] * len(supervised_docs)
            supervised_tuple = [
                (
                    sup_file,
                    get_csv_source_id(
                        (
                            unsup_file
                            if not doc_type == "nfs"
                            else os.path.join(nfs_base_path, unsup_file[1:])
                        ),
                        extra_options.get("csv_id_column"),
                        extra_options.get("csv_strong_columns"),
                        extra_options.get("csv_weak_columns"),
                        extra_options.get("csv_reference_columns"),
                        file_metadata,
                    ),
                )
                for (sup_file, unsup_file), file_metadata in zip(
                    supervised_docs, metadata
                )
            ]
        else:
            supervised_tuple = []
        return self._bazaar_client.train(
            model_name=model_name,
            unsupervised_docs=unsupervised_docs,
            supervised_docs=supervised_tuple,
            test_doc=test_doc,
            doc_type=doc_type,
            train_extra_options=extra_options,
            base_model_identifier=base_model_identifier,
            is_async=is_async,
            metadata=metadata,
        )

    def deploy(
        self,
        model_identifier: str,
        deployment_name: str,
        is_async: bool = True,
    ):
        """
        Deploys a model.

        Parameters:
        model_identifier (str): Identifier of the model to be deployed.
        deployment_name (str): Name of the deployment.
        is_async (bool, optional): Whether the deployment should be asynchronous.
        """
        print("*" * 50 + f" Deploying the model {model_identifier} " + "*" * 50)
        return self._bazaar_client.deploy(
            model_identifier=model_identifier,
            deployment_name=deployment_name,
            is_async=is_async,
        )
