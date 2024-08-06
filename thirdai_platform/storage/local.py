import os
import shutil

from storage.interface import StorageInterface
from storage.utils import create_token, verify_token


class LocalStorage(StorageInterface):
    def __init__(self, root: str):
        self.root = root

    def create_upload_token(self, model_identifier, user_id, model_id, expiration_min):
        return create_token(
            expiration_min=expiration_min,
            model_identifier=model_identifier,
            user_id=user_id,
            model_id=model_id,
        )

    def verify_upload_token(self, token):
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
        extension = f"{model_type}.zip" if compressed else model_type
        filepath = os.path.join(self.root, f"models/{model_id}/model.{extension}")

        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(block_size)
                if not chunk:
                    break
                yield chunk

    def delete(self, model_id: str):
        model_dir = os.path.join(self.root, f"models/{model_id}")
        if os.path.exists(model_dir):
            shutil.rmtree(model_dir)

        data_dir = os.path.join(self.root, f"data/{model_id}")
        if os.path.exists(data_dir):
            shutil.rmtree(data_dir)

        checkpoint_dir = os.path.join(self.root, str(model_id))
        if os.path.exists(checkpoint_dir):
            shutil.rmtree(checkpoint_dir)
