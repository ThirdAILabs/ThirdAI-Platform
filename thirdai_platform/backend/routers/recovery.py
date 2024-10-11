import json
import os
import traceback
from pathlib import Path
from typing import Optional

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
from platform_common.requests import response
from pydantic import BaseModel, Field, root_validator

recovery_router = APIRouter()


class BackupConfig(BaseModel):
    """
    Unified backup configuration class that dynamically validates required fields
    based on the cloud provider type (or if no cloud provider is used for local backups).
    """

    cloud_provider: Optional[str] = Field(
        None, description="Cloud provider (s3, azure, gcp, or empty for local)"
    )
    bucket_name: Optional[str] = Field(
        None, description="Cloud bucket name (for cloud providers)"
    )
    interval_minutes: Optional[int] = Field(
        None, description="For scheduling backups at intervals"
    )
    backup_limit: Optional[int] = Field(5, description="Number of backups to retain")

    # Cloud-specific fields (conditionally required based on cloud_provider)
    aws_access_key: Optional[str] = Field(None, description="AWS Access Key (for s3)")
    aws_secret_access_key: Optional[str] = Field(
        None, description="AWS Secret Key (for s3)"
    )
    azure_account_name: Optional[str] = Field(
        None, description="Azure Storage Account Name (for azure)"
    )
    azure_account_key: Optional[str] = Field(
        None, description="Azure Storage Account Key (for azure)"
    )
    gcp_credentials_file_path: Optional[str] = Field(
        None, description="GCP Credentials JSON File Path (for gcp)"
    )

    @root_validator(pre=True)
    def validate_config(cls, values):
        cloud_provider = values.get("cloud_provider")

        if cloud_provider == "s3":
            # For S3, ensure AWS keys are provided
            if not values.get("aws_access_key") or not values.get(
                "aws_secret_access_key"
            ):
                raise ValueError(
                    "AWS credentials (access key and secret key) are required for S3 backups."
                )
            if not values.get("bucket_name"):
                raise ValueError("Bucket name is required for S3 backups.")

        elif cloud_provider == "azure":
            # For Azure, ensure account name and key are provided
            if not values.get("azure_account_name") or not values.get(
                "azure_account_key"
            ):
                raise ValueError(
                    "Azure account name and key are required for Azure backups."
                )
            if not values.get("bucket_name"):
                raise ValueError("Bucket name is required for Azure backups.")

        elif cloud_provider == "gcp":
            # For GCP, ensure the credentials file path is provided
            if not values.get("gcp_credentials_file_path"):
                raise ValueError(
                    "GCP credentials file path is required for GCP backups."
                )
            if not values.get("bucket_name"):
                raise ValueError("Bucket name is required for GCP backups.")

        elif cloud_provider is None:
            # Local backup: no cloud provider means local backup, no extra fields required
            pass

        else:
            raise ValueError(f"Unsupported cloud provider: {cloud_provider}")

        return values

    def save_backup_config(self, model_bazaar_dir):
        config_path = os.path.join(model_bazaar_dir, "backup_config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        # Use dict() and json.dump to save the config to a file
        with open(config_path, "w") as file:
            json.dump(self.dict(), file, indent=4)

        return config_path


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
            recovery_snapshot_script="recovery_snapshot_job/run.py",
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
