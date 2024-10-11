from typing import Dict, List

import docker
from utils import Credentials


class CloudProviderInterface:
    def authorize_credentials(self, credentials: Credentials):
        self.credentials = credentials

    def build_image(
        self,
        dockerfile_path: str,
        context_path: str,
        tag: str,
        nocache: bool,
        buildargs: Dict[str, str],
    ) -> str:
        raise NotImplementedError

    def push_image(self, image_id: str, tag: str) -> None:
        raise NotImplementedError

    def get_image_digest(self, name: str, tag: str) -> List[str]:
        raise NotImplementedError

    def delete_image(self, repository: str, tag: str, **kwargs) -> None:
        raise NotImplementedError

    def create_credentials(
        self, name: str, image_names: List[str], push_access: bool
    ) -> Dict[str, str]:
        raise NotImplementedError

    def update_credentials(
        self, name: str, image_names: List[str], push_access: bool
    ) -> None:
        raise NotImplementedError

    def update_image(self, image_id: str, name: str, tag: str) -> None:
        raise NotImplementedError

    def get_registry_name(self) -> str:
        raise NotImplementedError

    def get_full_image_name(self, base_name: str, branch: str, tag: str) -> str:
        raise NotImplementedError

    def get_local_image_digest(self, image_id: str):
        client = docker.from_env()
        image = client.images.get(image_id)
        digest = image.attrs["RootFS"]["Layers"]
        return digest
