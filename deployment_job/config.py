from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


class ModelType(str, Enum):
    NDB = "ndb"
    UDT = "udt"
    ENTERPRISE_SEARCH = "enterprise-search"


class NDBSubType(str, Enum):
    v1 = "v1"
    v2 = "v2"


class UDTSubType(str, Enum):
    text = "text"
    token = "token"


class NDBDeploymentOptions(BaseModel):
    model_type: Literal[ModelType.NDB] = ModelType.NDB

    ndb_sub_type: NDBSubType = NDBSubType.v2

    llm_provider: str = "openai"
    genai_key: Optional[str] = None


class UDTDeploymentOptions(BaseModel):
    model_type: Literal[ModelType.UDT] = ModelType.UDT

    udt_sub_type: UDTSubType


class EnterpriseSearchOptions(BaseModel):
    model_type: Literal[ModelType.ENTERPRISE_SEARCH] = ModelType.ENTERPRISE_SEARCH

    retrieval_id: str
    guardrail_id: Optional[str] = None


class DeploymentConfig(BaseModel):
    model_id: str
    model_bazaar_endpoint: str
    model_bazaar_dir: str
    license_key: str

    autoscaling_enabled: bool = False

    model_options: Union[
        NDBDeploymentOptions, UDTDeploymentOptions, EnterpriseSearchOptions
    ] = Field(..., discriminator="model_type")

    def get_nomad_endpoint(self) -> str:
        # Parse the model_bazaar_endpoint to extract scheme and host
        from urllib.parse import urlparse, urlunparse

        parsed_url = urlparse(self.model_bazaar_endpoint)

        # Reconstruct the URL with port 4646
        nomad_netloc = f"{parsed_url.hostname}:4646"

        # Rebuild the URL while keeping the original scheme and hostname
        return urlunparse((parsed_url.scheme, nomad_netloc, "", "", "", ""))
