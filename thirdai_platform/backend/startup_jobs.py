import os
from pathlib import Path

from backend.utils import nomad_job_exists, delete_nomad_job, get_platform, submit_nomad_job, get_empty_port, get_python_path, get_root_absolute_path

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
        python_path=get_python_path(),
        generate_app_dir=str(get_root_absolute_path() / "llm_generation_job"),
    )


STATUS_SYNC_JOB_ID = "status-sync"


async def restart_status_sync_job():
    """
    Restart the Status Sync Job

    Returns:
    - Response: The response from the Nomad API.
    """
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
    if nomad_job_exists(STATUS_SYNC_JOB_ID, nomad_endpoint):
        delete_nomad_job(STATUS_SYNC_JOB_ID, nomad_endpoint)
    cwd = Path(os.getcwd())
    platform = get_platform()
    return submit_nomad_job(
        nomad_endpoint=nomad_endpoint,
        filepath=str(cwd / "backend" / "nomad_jobs" / "status_sync_job.hcl.j2"),
        platform=platform,
        port=None if platform == "docker" else get_empty_port(),
        tag=os.getenv("TAG"),
        registry=os.getenv("DOCKER_REGISTRY"),
        docker_username=os.getenv("DOCKER_USERNAME"),
        docker_password=os.getenv("DOCKER_PASSWORD"),
        model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT"),
        image_name=os.getenv("STATUS_SYNC_IMAGE_NAME"),
        train_script=str(get_root_absolute_path() / "status_sync_job/sync_status.py"),
        python_path=get_python_path(),
        generate_app_dir=str(get_root_absolute_path() / "status_sync_job"),
    )