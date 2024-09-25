import os
import shutil
import zipfile

from storage.interface import StorageInterface
from storage.utils import create_token, verify_token


class LocalStorage(StorageInterface):
    def __init__(self, root: str):
        """
        Initializes the LocalStorage instance.

        Parameters:
        - root: str - The root directory for storing models.
            Example: "/path/to/storage"
        """
        self.root = root

    def create_upload_token(self, model_identifier, user_id, model_id, expiration_min):
        """
        Creates an upload token for a model.

        Parameters:
        - model_identifier: str - The unique identifier for the model.
            Example: "user123/my_model"
        - user_id: str - The ID of the user uploading the model.
            Example: "user123"
        - model_id: str - The ID of the model to be uploaded.
            Example: "model456"
        - expiration_min: int - The expiration time of the token in minutes.
            Example: 15

        Returns:
        - str: The upload token.
        """
        return create_token(
            expiration_min=expiration_min,
            model_identifier=model_identifier,
            user_id=user_id,
            model_id=model_id,
        )

    def verify_upload_token(self, token):
        """
        Verifies the given upload token.

        Parameters:
        - token: str - The upload token to verify.
            Example: "eyJhbGciOiJIUzI1NiIsInR5cCI..."

        Returns:
        - dict: The payload of the token if valid.
        """
        payload = verify_token(token)
        if (
            "model_identifier" not in payload
            or "user_id" not in payload
            or "model_id" not in payload
        ):
            raise ValueError("Token is invalid.")
        return payload

    def upload_chunk(
        self,
        model_id: str,
        chunk_data: bytes,
        chunk_number: int,
        model_type: str = "ndb",
        compressed: bool = True,
    ):
        """
        Uploads a chunk of the model.

        Parameters:
        - model_id: str - The ID of the model.
            Example: "model456"
        - chunk_data: bytes - The raw bytes of the chunk.
        - chunk_number: int - The position of the chunk.
            Example: 1
        - model_type: str - The type of the model (default: "ndb").
            Example: "ndb"
        - compressed: bool - Whether the chunk is compressed (default: True).
            Example: True
        """
        extension = f"{model_type}.zip" if compressed else model_type
        chunk_filepath = f"models/{model_id}/model.{extension}.part{chunk_number}"
        chunk_path = os.path.join(self.root, chunk_filepath)
        os.makedirs(os.path.dirname(chunk_path), exist_ok=True)

        with open(chunk_path, "wb") as f:
            f.write(chunk_data)

    def commit_upload(
        self,
        model_id: str,
        total_chunks: int,
        model_type: str = "ndb",
        compressed: bool = True,
    ):
        """
        Commits the upload after all chunks have been uploaded.

        Parameters:
        - model_id: str - The ID of the model.
            Example: "model456"
        - total_chunks: int - The total number of chunks uploaded.
            Example: 10
        - model_type: str - The type of the model (default: "ndb").
            Example: "ndb"
        - compressed: bool - Whether the model is compressed (default: True).
            Example: True
        """
        extension = f"{model_type}.zip" if compressed else model_type
        filepath = os.path.join(self.root, f"models/{model_id}/model.{extension}")

        with open(filepath, "wb") as final_file:
            for i in range(1, total_chunks + 1):
                chunk_path = f"{filepath}.part{i}"

                with open(chunk_path, "rb") as chunk_file:
                    final_file.write(chunk_file.read())

                os.remove(chunk_path)

    def prepare_download(
        self, model_id: str, model_type: str = "ndb", compressed: bool = True
    ):
        """
        Prepares the model for download.

        Parameters:
        - model_id: str - The ID of the model.
            Example: "model456"
        - model_type: str - The type of the model (default: "ndb").
            Example: "ndb"
        - compressed: bool - Whether the model is compressed (default: True).
            Example: True
        """
        extension = f"{model_type}.zip" if compressed else model_type
        file_path = os.path.join(self.root, f"models/{model_id}/model.{extension}")

        if compressed:
            if not os.path.exists(file_path):
                uncompressed_path = os.path.join(
                    self.root, f"models/{model_id}/model.{model_type}"
                )
                if not os.path.exists(uncompressed_path):
                    raise ValueError("Failure to find saved model.")
                shutil.make_archive(uncompressed_path, "zip", uncompressed_path)
        else:
            if not os.path.exists(file_path):
                raise ValueError("Failure to find saved model.")

    def download_chunk_stream(
        self,
        model_id: str,
        block_size: int = 8192,
        model_type: str = "ndb",
        compressed: bool = True,
    ):
        """
        Streams the download of the model in chunks.

        Parameters:
        - model_id: str - The ID of the model.
            Example: "model456"
        - block_size: int - The size of each chunk in bytes (default: 8192).
            Example: 8192
        - model_type: str - The type of the model (default: "ndb").
            Example: "ndb"
        - compressed: bool - Whether the model is compressed (default: True).
            Example: True

        Returns:
        - generator: A generator that yields chunks of the model.
        """
        extension = f"{model_type}.zip" if compressed else model_type
        filepath = os.path.join(self.root, f"models/{model_id}/model.{extension}")

        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(block_size)
                if not chunk:
                    break
                yield chunk

    def delete(self, model_id: str):
        """
        Deletes the model.

        Parameters:
        - model_id: str - The ID of the model.
            Example: "model456"
        """
        model_dir = os.path.join(self.root, f"models/{model_id}")
        if os.path.exists(model_dir):
            shutil.rmtree(model_dir)

        data_dir = os.path.join(self.root, f"data/{model_id}")
        if os.path.exists(data_dir):
            shutil.rmtree(data_dir)

        checkpoint_dir = os.path.join(self.root, str(model_id))
        if os.path.exists(checkpoint_dir):
            shutil.rmtree(checkpoint_dir)

    def logs(self, model_id: str):
        model_dir = os.path.join(self.root, f"models/{model_id}")
        if not os.path.exists(model_dir):
            raise ValueError(f"Model with ID {model_id} does not exist.")

        zip_filepath = os.path.join(self.root, "logs.zip")

        with zipfile.ZipFile(zip_filepath, "w") as zipf:
            # Traverse the directory structure and add all log files to the zip
            for root, _, files in os.walk(model_dir):
                for file in files:
                    if file.endswith(".log"):  # Filter for log files
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(
                            file_path, model_dir
                        )  # Relative path for the zip file structure
                        zipf.write(file_path, arcname)

        return zip_filepath
