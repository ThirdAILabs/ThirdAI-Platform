import logging
import os
import shutil
from pathlib import Path
from typing import Optional

import yaml
from auth.utils import get_hostname_from_url
from backend.utils import (
    get_platform,
    get_python_path,
    get_root_absolute_path,
    nomad_job_exists,
    submit_nomad_job,
    thirdai_platform_dir,
)
from platform_common.utils import model_bazaar_path

GENERATE_JOB_ID = "llm-generation"
THIRDAI_PLATFORM_FRONTEND_ID = "thirdai-platform-frontend"
TELEMETRY_ID = "telemetry"


async def restart_generate_job():
    """
    Restart the LLM generation job.

    Returns:
    - Response: The response from the Nomad API.
    """
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
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
        image_name=os.getenv("THIRDAI_PLATFORM_IMAGE_NAME"),
        model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT"),
        python_path=get_python_path(),
        thirdai_platform_dir=thirdai_platform_dir(),
        app_dir="llm_dispatch_job",
        share_dir=os.getenv("SHARE_DIR"),
    )


ON_PREM_GENERATE_JOB_ID = "on-prem-llm-generation"


async def start_on_prem_generate_job(
    model_name: str = "Llama-3.2-1B-Instruct-f16.gguf",
    restart_if_exists: bool = True,
    autoscaling_enabled: bool = True,
    cores_per_allocation: Optional[int] = None,
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
    share_dir = os.getenv("SHARE_DIR")
    if not share_dir:
        raise ValueError("SHARE_DIR variable is not set.")
    cwd = Path(os.getcwd())
    mount_dir = os.path.join(model_bazaar_path(), "pretrained-models/genai")
    model_path = os.path.join(mount_dir, model_name)
    if not os.path.exists(model_path):
        raise ValueError(f"Cannot find model at location: {model_path}.")
    model_size = int(os.path.getsize(model_path) / 1e6)
    # TODO(david) support configuration for multiple models
    job_memory_mb = model_size * 2  # give some leeway
    if os.cpu_count() < 8:
        raise ValueError("Can't run LLM job on less than 8 cores")
    if cores_per_allocation is None:
        cores_per_allocation = 7
    return submit_nomad_job(
        nomad_endpoint=nomad_endpoint,
        filepath=str(cwd / "backend" / "nomad_jobs" / "on_prem_generation_job.hcl.j2"),
        mount_dir=os.path.join(share_dir, "pretrained-models/genai"),
        initial_allocations=1,
        min_allocations=1,
        max_allocations=5,
        cores_per_allocation=cores_per_allocation,
        memory_per_allocation=job_memory_mb,
        model_name=model_name,
        registry=os.getenv("DOCKER_REGISTRY"),
        docker_username=os.getenv("DOCKER_USERNAME"),
        docker_password=os.getenv("DOCKER_PASSWORD"),
        autoscaling_enabled="true" if autoscaling_enabled else "false",
    )


async def start_llm_cache_job(model_id: str, deployment_name: str, license_info):
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
    cwd = Path(os.getcwd())
    platform = get_platform()
    return submit_nomad_job(
        nomad_endpoint=nomad_endpoint,
        filepath=str(cwd / "backend" / "nomad_jobs" / "llm_cache_job.hcl.j2"),
        platform=platform,
        tag=os.getenv("TAG"),
        registry=os.getenv("DOCKER_REGISTRY"),
        docker_username=os.getenv("DOCKER_USERNAME"),
        docker_password=os.getenv("DOCKER_PASSWORD"),
        image_name=os.getenv("THIRDAI_PLATFORM_IMAGE_NAME"),
        model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT"),
        share_dir=os.getenv("SHARE_DIR"),
        python_path=get_python_path(),
        thirdai_platform_dir=thirdai_platform_dir(),
        app_dir="llm_cache_job",
        license_key=license_info["boltLicenseKey"],
        model_id=model_id,
        deployment_name=deployment_name,
    )


async def restart_thirdai_platform_frontend():
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
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
        identity_provider=os.getenv("IDENTITY_PROVIDER", "postgres"),
        keycloak_server_hostname=get_hostname_from_url(
            os.getenv("KEYCLOAK_SERVER_URL")
        ),
        use_ssl_in_login=os.getenv("USE_SSL_IN_LOGIN", "False").lower(),
        share_dir=os.getenv("SHARE_DIR"),
        nextauth_secret=os.getenv("JWT_SECRET", "random secret"),
        # Model bazaar dockerfile does not include neuraldb_frontend code,
        # but app_dir is only used if platform == local.
        app_dir=str(get_root_absolute_path() / "frontend"),
        majority_critical_services_nodes=os.getenv(
            "MAJORITY_CRITICAL_SERVICE_NODES", "1"
        ),
    )


def create_promfile(promfile_path: str):
    platform = get_platform()
    model_bazaar_endpoint = os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT")
    nomad_nodes_dir = os.path.join(
        model_bazaar_path(), "nomad-monitoring", "nomad_nodes"
    )
    os.makedirs(nomad_nodes_dir, exist_ok=True)

    server_node_file = os.path.join(nomad_nodes_dir, "server.yaml")
    client_node_file = os.path.join(nomad_nodes_dir, "client.yaml")

    if platform == "local":
        # create the local server.yaml file
        with open(server_node_file, "w") as fp:
            yaml.dump(
                [
                    {
                        "targets": ["host.docker.internal:4646"],
                        "labels": {"nomad_node": "server"},
                    }
                ],
                fp,
                sort_keys=False,
            )

        deployment_targets_endpoint = (
            "http://host.docker.internal:80/api/telemetry/deployment-services"
        )
    else:
        """
        nomad_nodes: would be created by ansible installation script in dockerized environment
        """

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
                "file_sd_configs": [
                    {"files": ["/model_bazaar/nomad-monitoring/nomad_nodes/*.yaml"]}
                ],
                "relabel_configs": [
                    {
                        "source_labels": ["__address__"],
                        "regex": "([^:]+):.+",
                        "target_label": "hostname",
                        "replacement": "nomad-agent-${1}",
                    }
                ],
            },
            {
                "job_name": "deployment-jobs",
                "metrics_path": "/metrics",
                "http_sd_configs": [{"url": deployment_targets_endpoint}],
                "relabel_configs": [
                    {
                        "source_labels": ["model_id"],
                        "target_label": "workload",
                        "replacement": "deployment-${1}",
                    }
                ],
            },
        ],
    }
    os.makedirs(os.path.dirname(promfile_path), exist_ok=True)
    with open(promfile_path, "w") as file:
        yaml.dump(prometheus_config, file, sort_keys=False)

    logging.info(f"Prometheus configuration has been written to {promfile_path}")

    # returning the nodes running nomad
    node_private_ips = []
    with open(server_node_file, "r") as file:
        data = yaml.safe_load(file)
        for server_nodes in data:
            node_private_ips.extend(server_nodes["targets"])

    if os.path.exists(client_node_file):
        with open(client_node_file, "r") as file:
            data = yaml.safe_load(file)
            for client_nodes in data:
                node_private_ips.extend(client_nodes["targets"])

    return node_private_ips


async def restart_telemetry_jobs():
    """
    Restart the telemetry jobs.

    Returns:
    - Response: The response from the Nomad API.
    """
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")

    cwd = Path(os.getcwd())
    platform = get_platform()
    share_dir = os.getenv("SHARE_DIR")

    # Copying the grafana dashboards
    shutil.copytree(
        str(cwd / "grafana_dashboards"),
        os.path.join(model_bazaar_path(), "nomad-monitoring", "grafana_dashboards"),
        dirs_exist_ok=True,
    )
    promfile_path = os.path.join(
        model_bazaar_path(), "nomad-monitoring", "node_discovery", "prometheus.yaml"
    )

    # Creating prometheus config file
    targets = create_promfile(promfile_path)

    response = submit_nomad_job(
        nomad_endpoint=nomad_endpoint,
        filepath=str(cwd / "backend" / "nomad_jobs" / "telemetry.hcl.j2"),
        platform=platform,
        share_dir=share_dir,
        target_count=str(len(targets)),
        grafana_db_url=os.getenv("GRAFANA_DB_URL"),
        admin_username=os.getenv("ADMIN_USERNAME"),
        admin_password=os.getenv("ADMIN_PASSWORD"),
        admin_mail=os.getenv("ADMIN_MAIL"),
        registry=os.getenv("DOCKER_REGISTRY"),
        docker_username=os.getenv("DOCKER_USERNAME"),
        docker_password=os.getenv("DOCKER_PASSWORD"),
        model_bazaar_private_host=(
            "host.docker.internal"
            if platform == "local"
            else get_hostname_from_url(os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT"))
        ),
        vector_config_path=str(
            cwd / "backend" / "nomad_jobs" / "vector-config-jobs.yaml"
        ),
    )
    if response.status_code != 200:
        raise Exception(f"{response.text}")
