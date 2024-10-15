from dataclasses import dataclass


@dataclass
class Image:
    key: str
    name: str
    dockerfile_path: str
    context_path: str


images_to_build = [
    Image(
        key="THIRDAI_PLATFORM_IMAGE_NAME",
        name="thirdai_platform",
        dockerfile_path="Dockerfile",
        context_path="thirdai_platform",
    ),
    Image(
        key="FRONTEND_IMAGE_NAME",
        name="frontend",
        dockerfile_path="Dockerfile",
        context_path="frontend",
    ),
    Image(
        key="TRAIN_IMAGE_NAME",
        name="train_job",
        dockerfile_path="train_job/Dockerfile",
        context_path="thirdai_platform",
    ),
    Image(
        key="DEPLOY_IMAGE_NAME",
        name="deployment_job",
        dockerfile_path="deployment_job/Dockerfile",
        context_path="thirdai_platform",
    ),
    Image(
        key="DATA_GENERATION_IMAGE_NAME",
        name="data_generation_job",
        dockerfile_path="data_generation_job/Dockerfile",
        context_path="thirdai_platform",
    ),
    Image(
        key="GENERATION_IMAGE_NAME",
        name="llm_dispatch_job",
        dockerfile_path="llm_dispatch_job/Dockerfile",
        context_path="thirdai_platform",
    ),
    Image(
        key="LLM_CACHE_IMAGE_NAME",
        name="llm_cache_job",
        dockerfile_path="llm_cache_job/Dockerfile",
        context_path="thirdai_platform",
    ),
    Image(
        key="RECOVERY_SNAPSHOT_IMAGE_NAME",
        name="recovery_snapshot_job",
        dockerfile_path="recovery_snapshot_job/Dockerfile",
        context_path="thirdai_platform",
    ),
]


images_to_pull_from_private = ["victoria-metrics", "grafana", "loki", "llama.cpp"]
