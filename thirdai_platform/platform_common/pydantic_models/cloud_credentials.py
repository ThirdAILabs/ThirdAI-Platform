import logging
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# Define AWS credentials with environment variable defaults using BaseSettings
class AWSCredentials(BaseSettings):
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    region_name: Optional[str] = None

    class Config:
        env_prefix = "AWS_"  # Prefix for environment variables, e.g., AWS_ACCESS_KEY


# Define Azure credentials with environment variable defaults using BaseSettings
class AzureCredentials(BaseSettings):
    account_name: Optional[str] = None
    account_key: Optional[str] = None

    class Config:
        env_prefix = (
            "AZURE_"  # Prefix for environment variables, e.g., AZURE_ACCOUNT_NAME
        )


# Define GCP credentials with environment variable defaults using BaseSettings
class GCPCredentials(BaseSettings):
    credentials_file: Optional[str] = None

    class Config:
        env_prefix = (
            "GCP_"  # Prefix for environment variables, e.g., GCP_CREDENTIALS_FILE
        )


# Main CloudCredentials model using these credentials
class CloudCredentials(BaseModel):
    aws: Optional[AWSCredentials] = None
    azure: Optional[AzureCredentials] = None
    gcp: Optional[GCPCredentials] = None


class CredentialRegistry(BaseModel):
    credentials_map: Dict[str, CloudCredentials] = Field(default_factory=dict)

    def save_credentials(
        self, bucket_name: str, credentials: CloudCredentials, update: bool = False
    ):
        if not self.credentials_exists(bucket_name) or update:
            self.credentials_map[bucket_name] = credentials
        else:
            logging.warning("Credentials exists for the bucket, skipping update")

    def credentials_exists(self, bucket_name):
        return self.get_credentials(bucket_name) is not None

    def get_credentials(self, bucket_name: str) -> Optional[CloudCredentials]:
        return self.credentials_map.get(bucket_name)

    def remove_credentials(self, bucket_name: str):
        if bucket_name in self.credentials_map:
            del self.credentials_map[bucket_name]

    def save_to_disk(self, registry_path: Path):
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(registry_path, "w") as file:
            file.write(self.model_dump_json(indent=4))
