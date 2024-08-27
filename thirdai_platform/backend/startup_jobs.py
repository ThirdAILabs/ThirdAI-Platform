import os
import uuid
from pathlib import Path

from backend.utils import (
    delete_nomad_job,
    get_empty_port,
    get_platform,
    get_python_path,
    get_root_absolute_path,
    nomad_job_exists,
    submit_nomad_job,
)

GENERATE_JOB_ID = "llm-generation"


async def restart_generate_job():
    """
    Restart the LLM generation job.

    Returns:
    - Response: The response from the Nomad API.
    """
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
    if nomad_job_exists(GENERATE_JOB_ID, nomad_endpoint):
        delete_nomad_job(GENERATE_JOB_ID, nomad_endpoint)
    cwd = Path(os.getcwd())
    platform = get_platform()
    return submit_nomad_job(
        nomad_endpoint=nomad_endpoint,
        filepath=str(cwd / "backend" / "nomad_jobs" / "generation_job.hcl.j2"),
        platform=platform,
        port=None if platform == "docker" else get_empty_port(),
        tag=os.getenv("TAG"),
        registry=os.getenv("DOCKER_REGISTRY"),
        docker_username=os.getenv("DOCKER_USERNAME"),
        docker_password=os.getenv("DOCKER_PASSWORD"),
        image_name=os.getenv("GENERATION_IMAGE_NAME"),
        model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT"),
        python_path=get_python_path(),
        generate_app_dir=str(get_root_absolute_path() / "llm_generation_job"),
        model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT", None),
    )


ON_PREM_GENERATE_JOB_ID = "on-prem-llm-generation"


async def restart_on_prem_generate_job(model_name="qwen2-0_5b-instruct-fp16.gguf"):
    """
    Restart the LLM generation job.

    Returns:
    - Response: The response from the Nomad API.
    """
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
    if nomad_job_exists(ON_PREM_GENERATE_JOB_ID, nomad_endpoint):
        delete_nomad_job(ON_PREM_GENERATE_JOB_ID, nomad_endpoint)
    share_dir = os.getenv("SHARE_DIR")
    if not share_dir:
        raise ValueError("SHARE_DIR variable is not set.")
    cwd = Path(os.getcwd())
    mount_dir = os.path.join(share_dir, "gen-ai-models")
    model_path = os.path.join(mount_dir, model_name)
    if not os.path.exists(model_path):
        raise ValueError(f"Cannot find model at location: {model_path}.")
    return submit_nomad_job(
        nomad_endpoint=nomad_endpoint,
        filepath=str(cwd / "backend" / "nomad_jobs" / "on_prem_generation_job.hcl.j2"),
        docker_username=os.getenv("DOCKER_USERNAME"),
        docker_password=os.getenv("DOCKER_PASSWORD"),
        mount_dir=mount_dir,
        num_allocations=1,
        cores_per_allocation=10,
        model_name=model_name,
    )


LLM_CACHE_JOB_ID = "llm-cache"


async def restart_llm_cache_job():
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
    if nomad_job_exists(LLM_CACHE_JOB_ID, nomad_endpoint):
        delete_nomad_job(LLM_CACHE_JOB_ID, nomad_endpoint)
    cwd = Path(os.getcwd())
    platform = get_platform()
    return submit_nomad_job(
        nomad_endpoint=nomad_endpoint,
        filepath=str(cwd / "backend" / "nomad_jobs" / "llm_cache_job.hcl.j2"),
        platform=platform,
        port=None if platform == "docker" else get_empty_port(),
        tag=os.getenv("TAG"),
        registry=os.getenv("DOCKER_REGISTRY"),
        docker_username=os.getenv("DOCKER_USERNAME"),
        docker_password=os.getenv("DOCKER_PASSWORD"),
        image_name=os.getenv("LLM_CACHE_IMAGE_NAME"),
        model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT"),
        share_dir=os.getenv("SHARE_DIR"),
        python_path=get_python_path(),
        llm_cache_app_dir=str(get_root_absolute_path() / "llm_cache_job"),
    )
