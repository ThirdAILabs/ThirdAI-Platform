from dataclasses import dataclass


@dataclass
class Image:
    key: str
    name: str
    dockerfile_path: str


images_to_build = [
    Image("THIRDAI_PLATFORM_IMAGE_NAME", "thirdai_platform", "thirdai_platform"),
    Image("FRONTEND_IMAGE_NAME", "frontend", "frontend"),
    Image("TRAIN_IMAGE_NAME", "train_job", "thirdai_platform/train_job"),
    Image(
        "DEPLOY_IMAGE_NAME",
        "deployment_job",
        "thirdai_platform/deployment_job",
    ),
    Image(
        "DATA_GENERATION_IMAGE_NAME",
        "data_generation_job",
        "thirdai_platform/data_generation_job",
    ),
    Image(
        "GENERATION_IMAGE_NAME",
        "llm_dispatch_job",
        "thirdai_platform/llm_dispatch_job",
    ),
    Image(
        "LLM_CACHE_IMAGE_NAME",
        "llm_cache_job",
        "thirdai_platform/llm_cache_job",
    ),
]


images_to_pull_from_private = ["victoria-metrics", "grafana", "loki", "llama.cpp"]
