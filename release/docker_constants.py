class ImageNames:
    def __init__(self, **kwargs) -> None:
        """
        Initialize ImageNames with default and custom image names.

        :param kwargs: Additional image names provided as keyword arguments
        """
        self.THIRDAI_PLATFORM_IMAGE_NAME = "thirdai_platform"
        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_list(self) -> list:
        """
        Convert the image names to a list.

        :return: List of image names
        """
        return list(self.__dict__.values())

    def peripherals_as_dict(self) -> dict:
        """
        Convert peripheral image names to a dictionary excluding the platform image.

        :return: Dictionary of peripheral image names
        """
        as_dict = {attr: getattr(self, attr) for attr in self.__dict__}
        del as_dict["THIRDAI_PLATFORM_IMAGE_NAME"]
        return as_dict


# IMPORTANT: Image names are assumed to be the same as the directories that
# contain the Docker files. E.g., TRAIN_IMAGE_NAME=train_job, so the
# Dockerfile that defines this image is assumed to be found in
# train_job/.
image_base_names = ImageNames(
    TRAIN_IMAGE_NAME="train_job",
    DEPLOY_IMAGE_NAME="deployment_job",
    GENERATION_IMAGE_NAME="llm_generation_job",
    ON_PREM_GENERATION_IMAGE_NAME="on_prem_llm_generation_job",
)
