import os
import traceback
from pathlib import Path

from auth.jwt import verify_access_token
from backend.utils import (
    delete_nomad_job,
    get_platform,
    get_python_path,
    model_bazaar_path,
    nomad_job_exists,
    submit_nomad_job,
    thirdai_platform_dir,
)
from fastapi import APIRouter, Depends, HTTPException, status
from platform_common.pydantic_models.recovery_snapshot import BackupConfig
from platform_common.utils import response

recovery_router = APIRouter()


RECOVERY_SNAPSHOT_ID = "recovery-snapshot"


@recovery_router.post("/backup", dependencies=[Depends(verify_access_token)])
def backup(config: BackupConfig):
    local_dir = os.getenv("SHARE_DIR")
    if not local_dir:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SHARE_DIR environment variable is not set.",
        )

    db_uri = os.getenv("DATABASE_URI")
    if not db_uri:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DATABASE_URI environment variable is not set.",
        )

    # Save the configuration for future use
    config_file_path = config.save_backup_config(model_bazaar_path())

    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
    if nomad_job_exists(RECOVERY_SNAPSHOT_ID, nomad_endpoint):
        delete_nomad_job(RECOVERY_SNAPSHOT_ID, nomad_endpoint)
    cwd = Path(os.getcwd())
    platform = get_platform()
    try:
        submit_nomad_job(
            nomad_endpoint=nomad_endpoint,
            filepath=str(
                cwd / "backend" / "nomad_jobs" / "recovery_snapshot_job.hcl.j2"
            ),
            platform=platform,
            tag=os.getenv("TAG"),
            registry=os.getenv("DOCKER_REGISTRY"),
            docker_username=os.getenv("DOCKER_USERNAME"),
            docker_password=os.getenv("DOCKER_PASSWORD"),
            image_name=os.getenv("RECOVERY_SNAPSHOT_IMAGE_NAME"),
            model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT"),
            python_path=get_python_path(),
            thirdai_platform_dir=thirdai_platform_dir(),
            recovery_snapshot_script="recovery_snapshot_job.run",
            config_path=config_file_path,
            share_dir=local_dir,
            db_uri=db_uri,
        )
    except Exception as err:
        traceback.print_exc()
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=str(err)
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully submitted recovery snapshot job.",
    )
