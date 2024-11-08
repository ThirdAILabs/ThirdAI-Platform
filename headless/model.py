import os
from typing import Any, Dict, List, Optional, Tuple

from client.bazaar import ModelBazaar
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
        self._global_email = email
        self._global_password = password
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
        model_options: Optional[Dict[str, str]] = {},
        base_model_identifier: Optional[str] = None,
        is_async: bool = True,
        metadata: Optional[List[Dict[str, str]]] = None,
        nfs_base_path: Optional[str] = None,
        doc_options: Dict[str, Dict[str, Any]] = {},
        job_options: Optional[dict] = None,
    ):
        """
        Trains a model with the given documents and options.

        Parameters:
        model_name (str): Name of the model.
        unsupervised_docs (list[str], optional): List of paths to unsupervised documents.
        supervised_docs (list[tuple[str, str]], optional): List of tuples containing paths to supervised and unsupervised documents.
        test_doc (str, optional): Path to the test document.
        doc_type (str, optional): Type of documents (e.g., local, nfs).
        model_options (dict, optional): Model configuration options.
        base_model_identifier (str, optional): Identifier for the base model.
        is_async (bool, optional): Whether the training should be asynchronous.
        metadata (list[dict[str, str]], optional): Metadata for the documents.
        nfs_base_path (str, optional): Base path for NFS storage.
        doc_options (dict, optional): Document-specific options.
        job_options (dict, optional): Resource allocation options for the job.
        """

        print("*" * 50 + f" Training the model: {model_name} " + "*" * 50)

        # Prepare unsupervised_docs as FileInfo structures
        unsupervised_file_infos = [
            {
                "path": doc,
                "location": doc_type,
                "options": doc_options.get(doc, {}),
                "metadata": metadata[i] if metadata else None,
            }
            for i, doc in enumerate(unsupervised_docs or [])
        ]

        # Prepare supervised_docs as FileInfo structures with source IDs
        supervised_file_infos = []
        if supervised_docs:
            if metadata is None:
                metadata = [None] * len(supervised_docs)

            for (sup_file, unsup_file), file_metadata in zip(supervised_docs, metadata):
                source_id = get_csv_source_id(
                    (
                        unsup_file
                        if not doc_type == "nfs"
                        else os.path.join(nfs_base_path, unsup_file[1:])
                    ),
                    doc_options.get(unsup_file, {}).get("csv_id_column"),
                    doc_options.get(unsup_file, {}).get("csv_strong_columns"),
                    doc_options.get(unsup_file, {}).get("csv_weak_columns"),
                    doc_options.get(unsup_file, {}).get("csv_reference_columns"),
                    file_metadata,
                )
                supervised_file_infos.append(
                    {
                        "path": sup_file,
                        "doc_id": source_id,
                        "location": doc_type,
                        "options": doc_options.get(sup_file, {}),
                    }
                )

        # Prepare test_doc as a FileInfo structure if provided
        test_file_info = (
            {
                "path": test_doc,
                "location": doc_type,
                "options": doc_options.get(test_doc, {}),
            }
            if test_doc
            else None
        )

        return self._bazaar_client.train(
            model_name=model_name,
            unsupervised_docs=unsupervised_file_infos,
            supervised_docs=supervised_file_infos,
            test_doc=test_file_info,
            model_options=model_options,
            base_model_identifier=base_model_identifier,
            is_async=is_async,
            job_options=job_options,
        )
