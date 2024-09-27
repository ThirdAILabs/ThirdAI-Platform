import os
import shutil
from pathlib import Path

import requests
import yaml
from backend.utils import (
    delete_nomad_job,
    get_platform,
    get_python_path,
    get_root_absolute_path,
    model_bazaar_path,
    nomad_job_exists,
    response,
    submit_nomad_job,
)
from fastapi import status
from licensing.verify.verify_license import valid_job_allocation, verify_license

GENERATE_JOB_ID = "llm-generation"
THIRDAI_PLATFORM_FRONTEND_ID = "thirdai-platform-frontend"
LLM_CACHE_JOB_ID = "llm-cache"
TELEMETRY_ID = "telemetry"


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
    autoscaling_enabled=True,
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
    cwd = Path(os.getcwd())
    mount_dir = os.path.join(model_bazaar_path(), "gen-ai-models")
    model_path = os.path.join(mount_dir, model_name)
    if not os.path.exists(model_path):
        raise ValueError(f"Cannot find model at location: {model_path}.")
    model_size = int(os.path.getsize(model_path) / 1e6)
    job_memory_mb = model_size * 2  # give some leeway
    return submit_nomad_job(
        nomad_endpoint=nomad_endpoint,
        filepath=str(cwd / "backend" / "nomad_jobs" / "on_prem_generation_job.hcl.j2"),
        mount_dir=os.path.join(share_dir, "gen-ai-models"),
        initial_allocations=1,
        min_allocations=1,
        max_allocations=5,
        threads_http=2,
        cores_per_allocation=7,
        memory_per_allocation=job_memory_mb,
        model_name=model_name,
        registry=os.getenv("DOCKER_REGISTRY"),
        docker_username=os.getenv("DOCKER_USERNAME"),
        docker_password=os.getenv("DOCKER_PASSWORD"),
        autoscaling_enabled="true" if autoscaling_enabled else "false",
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


def create_promfile(promfile_path: str):
    platform = get_platform()
    model_bazaar_endpoint = os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT")
    if platform == "local":
        targets = ["host.docker.internal:4646"]

        deployment_targets_endpoint = (
            "http://host.docker.internal:80/api/telemetry/deployment-services"
        )
    else:
        nomad_url = f"{model_bazaar_endpoint.rstrip('/')}:4646/v1/nodes"

        # Fetch the node data from Nomad
        headers = {"X-Nomad-Token": os.getenv("MANAGEMENT_TOKEN")}
        response = requests.get(nomad_url, headers=headers)
        nodes = response.json()

        targets = [f"{node['Address']}:4646" for node in nodes]

        deployment_targets_endpoint = (
            f"{model_bazaar_endpoint.rstrip('/')}/api/telemetry/deployment-services"
        )

    # Prometheus template
    prometheus_config = {
        "global": {
            "scrape_interval": "1s",
            "external_labels": {"env": "dev", "cluster": "local"},
        },
        "scrape_configs": [
            {
                "job_name": "nomad-agent",
                "metrics_path": "/v1/metrics?format=prometheus",
                "static_configs": [{"targets": targets, "labels": {"role": "agent"}}],
                "relabel_configs": [
                    {
                        "source_labels": ["__address__"],
                        "regex": "([^:]+):.+",
                        "target_label": "hostname",
                        "replacement": "nomad-agent-$1",
                    }
                ],
            },
            {
                "job_name": "deployment-jobs",
                "metrics_path": "/metrics",
                "http_sd_configs": [{"url": deployment_targets_endpoint}],
            },
        ],
    }
    os.makedirs(os.path.dirname(promfile_path), exist_ok=True)
    with open(promfile_path, "w") as file:
        yaml.dump(prometheus_config, file, sort_keys=False)

    print(f"Prometheus configuration has been written to {promfile_path}")
    return targets


async def restart_telemetry_jobs():
    """
    Restart the telemetry jobs.

    Returns:
    - Response: The response from the Nomad API.
    """
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
    if nomad_job_exists(TELEMETRY_ID, nomad_endpoint):
        delete_nomad_job(TELEMETRY_ID, nomad_endpoint)

    cwd = Path(os.getcwd())
    platform = get_platform()
    share_dir = os.getenv("SHARE_DIR")
    # Copying the telemetry dashboards if running on local
    if platform == "local":
        shutil.copytree(
            str(cwd / "telemetry_dashboards"),
            os.path.join(share_dir, "nomad-monitoring", "telemetry_dashboards"),
            dirs_exist_ok=True,
        )
        promfile_path = os.path.join(
            share_dir, "nomad-monitoring/node_discovery/prometheus.yaml"
        )
    else:
        promfile_path = "/model_bazaar/nomad-monitoring/node_discovery/prometheus.yaml"

    # Creating prometheus config file
    targets = create_promfile(promfile_path)

    response = submit_nomad_job(
        nomad_endpoint=nomad_endpoint,
        filepath=str(cwd / "backend" / "nomad_jobs" / "telemetry.hcl.j2"),
        platform=platform,
        promfile="/model_bazaar/nomad-monitoring/node_discovery/prometheus.yaml",  # Promfile_path could be different based on whether it is being run on `local-docker` or `docker`. But victoriametric should always find this file somewhere in the mounted volume. That's why it is being hardcoded here
        share_dir=share_dir,
        target_count=str(len(targets)),
        registry=os.getenv("DOCKER_REGISTRY"),
        docker_username=os.getenv("DOCKER_USERNAME"),
        docker_password=os.getenv("DOCKER_PASSWORD"),
    )
    if response.status_code != 200:
        raise Exception(f"{response.text}")
