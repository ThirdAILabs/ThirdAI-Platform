import json
import re
import subprocess
from typing import Dict, List, Optional

import docker
from azure.containerregistry import ContainerRegistryClient
from azure.identity import ClientSecretCredential
from cloud_provider_interface import CloudProviderInterface
from tqdm import tqdm
from utils import image_name_for_branch


class AzureProvider(CloudProviderInterface):
    def __init__(self, registry: str):
        """
        Initialize the AzureProvider with the registry URL.
        """
        self.registry = registry
        self.registry_name = registry.split(".")[0]

    def build_image(
        self,
        dockerfile_path: str,
        context_path: str,
        tag: str,
        nocache: bool,
        buildargs: Dict[str, str],
    ) -> str:
        """
        Build a Docker image from the specified path with the given tag.

        :param dockerfile_path: Path to the actual Dockerfile
        :param context_path: Path to the context used to build
        :param tag: Tag for the built image
        :param nocache: Whether to use cache during build
        :param buildargs: Build arguments for the Docker build
        :return: ID of the built image
        """
        print(f"Building image at path: {context_path} with tag: {tag}")
        docker_client = docker.APIClient(base_url="unix://var/run/docker.sock")
        generator = docker_client.build(
            path=context_path,
            dockerfile=dockerfile_path,
            tag=tag,
            rm=True,
            platform="linux/x86_64",
            nocache=nocache,
            buildargs=buildargs,
        )
        image_id: Optional[str] = None
        for chunk in generator:
            for minichunk in chunk.strip(b"\r\n").split(b"\r\n"):
                json_chunk = json.loads(minichunk)
                if "stream" in json_chunk:
                    print(json_chunk["stream"].strip())
                    match = re.search(
                        r"(^Successfully built |sha256:)([0-9a-f]+)$",
                        json_chunk["stream"],
                    )
                    if match:
                        image_id = match.group(2)
                if "errorDetail" in json_chunk:
                    raise RuntimeError(json_chunk["errorDetail"]["message"])
        if not image_id:
            raise RuntimeError(f"Did not successfully build {tag} from {context_path}")

        print(f"\nLocal: Built {image_id}\n")
        print("\n===============================================================\n")

        return image_id

    def push_image(self, image_id: str, tag: str) -> None:
        """
        Push a Docker image to the registry.

        :param image_id: ID of the image to push
        :param tag: Tag for the image in the registry
        """
        client = docker.from_env()
        client.login(
            username=self.credentials.push_username,
            password=self.credentials.push_password,
            registry=self.registry,
        )
        image = client.images.get(image_id)
        image.tag(tag)
        print(f"Pushing image with id {image_id} to {tag}")
        progress_bar = None
        total_size = None
        last_progress = 0

        for line in client.images.push(tag, stream=True, decode=True):
            if "status" in line and "progressDetail" in line:
                progress_detail = line["progressDetail"]
                current = progress_detail.get("current", 0)
                total = progress_detail.get("total", 0)

                if total_size is None and total > 0:
                    total_size = total
                    progress_bar = tqdm(
                        total=total_size,
                        unit="B",
                        unit_scale=True,
                        desc=f"Pushing {tag}",
                    )

                if progress_bar:
                    increment = current - last_progress
                    if increment > 0:
                        progress_bar.update(increment)
                        last_progress = current
            elif "status" in line and "progressDetail" not in line:
                if progress_bar:
                    progress_bar.close()
                print(line["status"])
            elif "errorDetail" in line:
                if progress_bar:
                    progress_bar.close()
                raise RuntimeError(line["errorDetail"]["message"])

        if progress_bar:
            progress_bar.close()

    def get_image_digest(self, name: str, tag: str) -> Optional[List[str]]:
        """
        Get the digest of a Docker image.

        :param name: Name of the image
        :param tag: Tag of the image
        :return: List of layer digests or None if the image is not found
        """
        client = docker.from_env()
        client.login(
            username=self.credentials.pull_username,
            password=self.credentials.pull_password,
            registry=self.registry,
        )
        image_full_name = f"{self.registry}/{name}:{tag}"
        try:
            image = client.images.pull(image_full_name)
            digest = image.attrs["RootFS"]["Layers"]
            return digest
        except docker.errors.ImageNotFound as e:
            print(f"{image_full_name} not found: {e}")
            return None
        except docker.errors.NotFound as e:
            print(f"{image_full_name} not found: {e}")
            return None

    def delete_image(self, repository: str, tag: str, **kwargs) -> None:
        """
        Delete a tag of an image from the Azure Container Registry.

        :param repository: Name of the repository
        :param tag: Tag of the image to delete
        :param kwargs: Additional keyword arguments (tenant_id, client_id, client_secret)
        """
        credential = ClientSecretCredential(
            tenant_id=kwargs.get("tenant_id"),
            client_id=kwargs.get("client_id"),
            client_secret=kwargs.get("client_secret"),
        )
        registry_client = ContainerRegistryClient(self.registry, credential)
        registry_client.delete_tag(repository, tag)

    def create_credentials(
        self, name: str, image_names: List[str], push_access: bool
    ) -> Dict[str, str]:
        """
        Create credentials for pushing and pulling images.

        :param name: Name for the scope map and token
        :param image_names: List of image names the credentials should have access to
        :param push_access: Whether the credentials should have push access
        :return: Dictionary with username and password
        """
        check_scope_map_cmd = (
            "az acr scope-map show"
            f" --name {name}"
            f" --registry {self.registry_name}"
            " --output json"
        )
        p = subprocess.Popen(
            [check_scope_map_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=True,
        )
        out = p.stdout.read()
        if out:
            raise Exception(
                f"Scope map with the given name {name} already exists. Please reuse those credentials instead, or use a new name."
            )

        check_token_cmd = (
            "az acr token show"
            f" --name {name}"
            f" --registry {self.registry_name}"
            " --output json"
        )
        p = subprocess.Popen(
            [check_token_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=True,
        )
        out = p.stdout.read()
        if out:
            raise Exception(
                f"Token with the given name {name} already exists. Please reuse those credentials instead, or use a new name."
            )

        make_scope_map_cmd = (
            "az acr scope-map create"
            f" --name {name}"
            f" --registry {self.registry_name}"
            " --output json"
        )
        for image_name in image_names:
            make_scope_map_cmd += (
                f" --repository {image_name} content/read metadata/read"
            )
            if push_access:
                make_scope_map_cmd += " content/write metadata/write content/delete"
        p = subprocess.Popen([make_scope_map_cmd], stdout=subprocess.PIPE, shell=True)
        out = p.stdout.read()
        print(out)

        make_token_cmd = (
            "az acr token create"
            f" --name {name}"
            f" --registry {self.registry_name}"
            f" --scope-map {name}"
            " --output json"
        )
        p = subprocess.Popen([make_token_cmd], stdout=subprocess.PIPE, shell=True)
        out = p.stdout.read()
        out = json.loads(out)
        username = out["credentials"]["username"]
        password = out["credentials"]["passwords"][0]["value"]

        return {"username": username, "password": password}

    def update_credentials(
        self, name: str, image_names: List[str], push_access: bool
    ) -> None:
        """
        Update credentials for pushing and pulling images.

        :param name: Name for the scope map and token
        :param image_names: List of image names the credentials should have access to
        :param push_access: Whether the credentials should have push access
        """
        check_scope_map_cmd = (
            "az acr scope-map show"
            f" --name {name}"
            f" --registry {self.registry_name}"
            " --output json"
        )
        p = subprocess.Popen(
            [check_scope_map_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=True,
        )
        out = p.stdout.read()
        if not out:
            raise Exception(
                f"Scope map with the given name {name} does not exist. Please first create a scope map named {name}."
            )

        check_token_cmd = (
            "az acr token show"
            f" --name {name}"
            f" --registry {self.registry_name}"
            " --output json"
        )
        p = subprocess.Popen(
            [check_token_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=True,
        )
        out = p.stdout.read()
        if not out:
            raise Exception(
                f"Token with the given name {name} does not exist. Please first create a token named {name}."
            )

        update_scope_map_cmd = (
            "az acr scope-map update"
            f" --name {name}"
            f" --registry {self.registry_name}"
            " --output json"
        )
        for image_name in image_names:
            update_scope_map_cmd += (
                f" --add-repository {image_name} content/read metadata/read"
            )
            if push_access:
                update_scope_map_cmd += " content/write metadata/write content/delete"
        p = subprocess.Popen([update_scope_map_cmd], stdout=subprocess.PIPE, shell=True)
        out = p.stdout.read()
        print(out)

    def update_image(self, image_id: str, name: str, tag: str) -> None:
        """
        Update an image with a new name and tag.

        :param image_id: ID of the image to update
        :param name: New name for the image
        :param tag: New tag for the image
        """
        client = docker.from_env()
        client.login(
            username=self.credentials.push_username,
            password=self.credentials.push_password,
            registry=self.registry,
        )
        image = client.images.get(image_id)
        image.tag(name, tag)
        for line in client.images.push(name, stream=True, decode=True):
            print(line)

    def get_registry_name(self) -> str:
        """
        Get the registry name.

        :return: Registry name
        """
        return self.registry

    def get_full_image_name(self, base_name: str, branch: str, tag: str) -> str:
        """
        Get the full image name for a given base name, branch, and tag.

        :param base_name: Base name of the image
        :param branch: Branch name
        :param tag: Tag for the image
        :return: Full image name
        """
        image_name = f"{self.registry}/{image_name_for_branch(base_name, branch)}:{tag}"
        return image_name
