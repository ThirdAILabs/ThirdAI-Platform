class ImageNames:
    def __init__(self, **kwargs) -> None:
        """
        Initialize ImageNames with default and custom image names and Dockerfile paths.

        :param kwargs: Additional image names and paths provided as keyword arguments
        """
        self.THIRDAI_PLATFORM_IMAGE_NAME = ("thirdai_platform", "thirdai_platform/Dockerfile")
        for key, value in kwargs.items():
            if isinstance(value, tuple) and len(value) == 2:
                setattr(self, key, value)
            else:
                raise ValueError(f"Each value must be a tuple of (image_name, dockerfile_path). Got {value} for {key}")

    def to_list(self) -> list:
        """
        Convert the image names to a list.

        :return: List of image names
        """
        return [name for name, _ in self.__dict__.values()]

    def get_dockerfile_path(self, image_name: str) -> str:
        """
        Get the Dockerfile path for a given image name.

        :param image_name: Name of the image
        :return: Path to the Dockerfile
        """
        for attr, (name, path) in self.__dict__.items():
            if name == image_name:
                return path
        raise ValueError(f"No Dockerfile path found for image name: {image_name}")

    def peripherals_as_dict(self) -> dict:
        """
        Convert peripheral image names to a dictionary excluding the platform image.

        :return: Dictionary of peripheral image names
        """
        as_dict = {attr: name for attr, (name, _) in self.__dict__.items() if attr != "THIRDAI_PLATFORM_IMAGE_NAME"}
        return as_dict

image_base_names = ImageNames(
    DATA_GENERATION_IMAGE_NAME=("data_generation_job", "data_gen/Dockerfile"),
    TRAIN_IMAGE_NAME=("train_job", "training/Dockerfile"),
    DEPLOY_IMAGE_NAME=("deployment_job", "deploy/Dockerfile"),
    GENERATION_IMAGE_NAME=("llm_dispatch_job", "llm/dispatch/Dockerfile"),
    FRONTEND_IMAGE_NAME=("frontend", "frontend/Dockerfile"),
    LLM_CACHE_IMAGE_NAME=("llm_cache_job", "llm/cache/Dockerfile"),
)

images_to_pull_from_private = ["victoria-metrics", "grafana", "loki", "llama.cpp"]
