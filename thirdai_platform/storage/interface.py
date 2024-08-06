class StorageInterface:
    def create_upload_token(self, model_identifier, user_id, model_id, expiration_min):
        raise NotImplementedError

    def verify_upload_token(self, token):
        raise NotImplementedError

    def upload_chunk(
        self,
        model_id: str,
        chunk_data: bytes,
        chunk_number: int,
        model_type: str,
        compressed: bool,
    ):
        raise NotImplementedError

    def commit_upload(
        self, model_id: str, total_chunks: int, model_type: str, compressed: bool
    ):
        raise NotImplementedError

    def prepare_download(self, model_id: str, model_type: str, compressed: bool):
        raise NotImplementedError

    def download_chunk_stream(
        self, model_id: str, block_size: int, model_type: str, compressed: bool
    ):
        raise NotImplementedError

    def delete(self, model_id: str):
        raise NotImplementedError
