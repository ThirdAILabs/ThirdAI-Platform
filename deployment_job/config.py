from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


class ModelType(str, Enum):
    NDB = "ndb"
    UDT = "udt"


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


class DeploymentConfig(BaseModel):
    model_id: str
    model_bazaar_endpoint: str
    model_bazaar_dir: str
    license_key: str
    task_runner_token: str

    autoscaling_enabled: bool = False

    model_options: Union[NDBDeploymentOptions, UDTDeploymentOptions] = Field(
        ..., discriminator="model_type"
    )
