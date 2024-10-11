from dataclasses import dataclass


@dataclass
class Image:
    key: str
    name: str
    dockerfile_path: str
    context_path: str


images_to_build = [
    Image(
        "THIRDAI_PLATFORM_IMAGE_NAME",
        "thirdai_platform",
        "thirdai_platform",
        "thirdai_platform",
    ),
    Image("FRONTEND_IMAGE_NAME", "frontend", "frontend", "frontend"),
    Image(
        "TRAIN_IMAGE_NAME",
        "train_job",
        "thirdai_platform/train_job",
        "thirdai_platform",
    ),
    Image(
        "DEPLOY_IMAGE_NAME",
        "deployment_job",
        "thirdai_platform/deployment_job",
        "thirdai_platform",
    ),
    Image(
        "DATA_GENERATION_IMAGE_NAME",
        "data_generation_job",
        "thirdai_platform/data_generation_job",
        "thirdai_platform",
    ),
    Image(
        "GENERATION_IMAGE_NAME",
        "llm_dispatch_job",
        "thirdai_platform/llm_dispatch_job",
        "thirdai_platform",
    ),
    Image(
        "LLM_CACHE_IMAGE_NAME",
        "llm_cache_job",
        "thirdai_platform/llm_cache_job",
        "thirdai_platform",
    ),
    Image(
        "RECOVERY_SNAPSHOT_IMAGE_NAME",
        "recovery_snapshot_job",
        "thirdai_platform/recovery_snapshot_job",
        "thirdai_platform",
    ),
]


images_to_pull_from_private = ["victoria-metrics", "grafana", "loki", "llama.cpp"]
