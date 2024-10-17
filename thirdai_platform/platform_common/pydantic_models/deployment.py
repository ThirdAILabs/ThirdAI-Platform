import os
from typing import Literal, Optional, Union

from platform_common.pydantic_models.training import ModelType, NDBSubType, UDTSubType
from pydantic import BaseModel, Field


class NDBDeploymentOptions(BaseModel):
    model_type: Literal[ModelType.NDB] = ModelType.NDB

    ndb_sub_type: NDBSubType = NDBSubType.v2

    llm_provider: str = "openai"
    genai_key: Optional[str] = None

    class Config:
        protected_namespaces = ()


class UDTDeploymentOptions(BaseModel):
    model_type: Literal[ModelType.UDT] = ModelType.UDT

    udt_sub_type: UDTSubType

    class Config:
        protected_namespaces = ()


class EnterpriseSearchOptions(BaseModel):
    model_type: Literal[ModelType.ENTERPRISE_SEARCH] = ModelType.ENTERPRISE_SEARCH

    retrieval_id: str
    guardrail_id: Optional[str] = None

    class Config:
        protected_namespaces = ()


class DeploymentConfig(BaseModel):
    model_id: str
    model_bazaar_endpoint: str
    model_bazaar_dir: str
    license_key: str

    autoscaling_enabled: bool = False

    model_options: Union[
        NDBDeploymentOptions, UDTDeploymentOptions, EnterpriseSearchOptions
    ] = Field(..., discriminator="model_type")

    class Config:
        protected_namespaces = ()

    def get_nomad_endpoint(self) -> str:
        # Parse the model_bazaar_endpoint to extract scheme and host
        from urllib.parse import urlparse, urlunparse

        parsed_url = urlparse(self.model_bazaar_endpoint)

        # Reconstruct the URL with port 4646
        nomad_netloc = f"{parsed_url.hostname}:4646"

        # Rebuild the URL while keeping the original scheme and hostname
        return urlunparse((parsed_url.scheme, nomad_netloc, "", "", "", ""))

    def save_deployment_config(self):
        config_path = os.path.join(
            self.model_bazaar_dir,
            "models",
            str(self.model_id),
            "deployments",
            "deployment_config.json",
        )
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as file:
            file.write(self.model_dump_json(indent=4))

        return config_path
