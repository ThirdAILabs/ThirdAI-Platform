from dataclasses import dataclass


@dataclass
class Image:
    """
    Represents a Docker image configuration for building and deployment.

    Attributes:
        name (str): The name of the image, used for tagging and identification.
        dockerfile_path (str): The path to the Dockerfile, relative to the context path.
        context_path (str): The build context path for Docker, typically the directory containing the Dockerfile and necessary files.
    """

    name: str
    dockerfile_path: str
    context_path: str


images_to_build = [
    Image(
        name="thirdai_platform",
        dockerfile_path="Dockerfile",
        context_path="thirdai_platform",
    ),
    Image(
        name="frontend",
        dockerfile_path="Dockerfile",
        context_path="frontend",
    ),
]


images_to_pull_from_private = ["victoria-metrics", "grafana", "loki", "llama.cpp"]
