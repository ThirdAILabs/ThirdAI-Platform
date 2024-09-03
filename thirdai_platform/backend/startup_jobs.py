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
    response,
    submit_nomad_job,
)
from fastapi import status
from licensing.verify.verify_license import valid_job_allocation, verify_license

GENERATE_JOB_ID = "llm-generation"
THIRDAI_PLATFORM_FRONTEND_ID = "thirdai-platform-frontend"
LLM_CACHE_JOB_ID = "llm-cache"


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
        filepath=str(cwd / "backend" / "nomad_jobs" / "llm_dispatch_job.hcl.j2"),
        platform=platform,
        tag=os.getenv("TAG"),
        registry=os.getenv("DOCKER_REGISTRY"),
        docker_username=os.getenv("DOCKER_USERNAME"),
        docker_password=os.getenv("DOCKER_PASSWORD"),
        image_name=os.getenv("GENERATION_IMAGE_NAME"),
        model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT"),
        python_path=get_python_path(),
        generate_app_dir=str(get_root_absolute_path() / "llm_dispatch_job"),
    )


ON_PREM_GENERATE_JOB_ID = "on-prem-llm-generation"


async def start_on_prem_generate_job(
    model_name="qwen2-0_5b-instruct-fp16.gguf",
    restart_if_exists=True,
):
    """
    Restart the LLM generation job.

    Returns:
    - Response: The response from the Nomad API.
    """
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
    if nomad_job_exists(ON_PREM_GENERATE_JOB_ID, nomad_endpoint):
        if not restart_if_exists:
            return
        delete_nomad_job(ON_PREM_GENERATE_JOB_ID, nomad_endpoint)
    share_dir = os.getenv("SHARE_DIR")
    if not share_dir:
        raise ValueError("SHARE_DIR variable is not set.")
    MODEL_BAZAAR_PATH = (
        "/model_bazaar"
        if os.path.exists("/.dockerenv")
        else os.getenv("SHARE_DIR", "/model_bazaar")
    )
    cwd = Path(os.getcwd())
    mount_dir = os.path.join(MODEL_BAZAAR_PATH, "gen-ai-models")
    model_path = os.path.join(mount_dir, model_name)
    if not os.path.exists(model_path):
        raise ValueError(f"Cannot find model at location: {model_path}.")
    return submit_nomad_job(
        nomad_endpoint=nomad_endpoint,
        filepath=str(cwd / "backend" / "nomad_jobs" / "on_prem_generation_job.hcl.j2"),
        mount_dir=os.path.join(share_dir, "gen-ai-models"),
        initial_allocations=1,
        min_allocations=1,
        max_allocations=5,
        threads_http=2,
        cores_per_allocation=10,
        memory_per_allocation=4000,
        model_name=model_name,
    )


async def restart_thirdai_platform_frontend():
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
    if nomad_job_exists(THIRDAI_PLATFORM_FRONTEND_ID, nomad_endpoint):
        delete_nomad_job(THIRDAI_PLATFORM_FRONTEND_ID, nomad_endpoint)
    cwd = Path(os.getcwd())
    return submit_nomad_job(
        nomad_endpoint=nomad_endpoint,
        filepath=str(
            cwd / "backend" / "nomad_jobs" / "thirdai_platform_frontend.hcl.j2"
        ),
        public_model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT"),
        openai_api_key=os.getenv("GENAI_KEY"),
        deployment_base_url=os.getenv("PUBLIC_MODEL_BAZAAR_ENDPOINT"),
        thirdai_platform_base_url=os.getenv("PUBLIC_MODEL_BAZAAR_ENDPOINT"),
        platform=get_platform(),
        tag=os.getenv("TAG"),
        registry=os.getenv("DOCKER_REGISTRY"),
        docker_username=os.getenv("DOCKER_USERNAME"),
        docker_password=os.getenv("DOCKER_PASSWORD"),
        image_name=os.getenv("FRONTEND_IMAGE_NAME"),
        # Model bazaar dockerfile does not include neuraldb_frontend code,
        # but app_dir is only used if platform == local.
        app_dir=str(get_root_absolute_path() / "frontend"),
    )


async def restart_llm_cache_job():
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
    if nomad_job_exists(LLM_CACHE_JOB_ID, nomad_endpoint):
        delete_nomad_job(LLM_CACHE_JOB_ID, nomad_endpoint)
    cwd = Path(os.getcwd())
    platform = get_platform()
    try:
        license_info = verify_license(
            os.getenv(
                "LICENSE_PATH", "/model_bazaar/license/ndb_enterprise_license.json"
            )
        )
        if not valid_job_allocation(license_info, os.getenv("NOMAD_ENDPOINT")):
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Resource limit reached, cannot allocate new jobs.",
            )
    except Exception as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"License is not valid. {str(e)}",
        )
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
        license_key=license_info["boltLicenseKey"],
    )
