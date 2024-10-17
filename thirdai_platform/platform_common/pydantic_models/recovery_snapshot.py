import json
import os
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


class S3Config(BaseModel):
    provider: Literal["s3"] = "s3"
    aws_access_key: str = Field(..., description="AWS Access Key (for s3)")
    aws_secret_access_key: str = Field(..., description="AWS Secret Key (for s3)")
    bucket_name: str = Field(..., description="S3 bucket name")


class AzureConfig(BaseModel):
    provider: Literal["azure"] = "azure"
    azure_account_name: str = Field(..., description="Azure Storage Account Name")
    azure_account_key: str = Field(..., description="Azure Storage Account Key")
    bucket_name: str = Field(..., description="Azure bucket/container name")


class GCPConfig(BaseModel):
    provider: Literal["gcp"] = "gcp"
    gcp_credentials_file_path: str = Field(
        ..., description="GCP Credentials JSON File Path"
    )
    bucket_name: str = Field(..., description="GCP bucket name")


class LocalBackupConfig(BaseModel):
    provider: Literal["local"] = "local"


# The main BackupConfig class that uses Union with discriminator
class BackupConfig(BaseModel):
    provider: Union[S3Config, AzureConfig, GCPConfig, LocalBackupConfig] = Field(
        ..., discriminator="provider"
    )
    interval_minutes: Optional[int] = Field(
        None, description="For scheduling backups at intervals"
    )
    backup_limit: Optional[int] = Field(5, description="Number of backups to retain")

    def save_backup_config(self, model_bazaar_dir):
        config_path = os.path.join(model_bazaar_dir, "backup_config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        # Use dict() and json.dump to save the config to a file
        with open(config_path, "w") as file:
            json.dump(self.dict(), file, indent=4)

        return config_path
