import ast
import datetime
import html
import os
from dataclasses import MISSING, asdict, dataclass, fields
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Type, TypeVar, Union, get_args, get_origin
from urllib.parse import urljoin

import requests
from fastapi import status
from utils import now

T = TypeVar("T", bound="EnvLoader")


class ModelType(str, Enum):
    NDB = "ndb"
    UDT = "udt"


class UDTSubType(str, Enum):
    token = "token"
    text = "text"


class NDBSubType(str, Enum):
    v1 = "v1"
    v2 = "v2"


class EnvLoader:
    type_mapping = {
        "ModelType": ModelType,
    }

    @classmethod
    def load_from_env(cls: Type[T]) -> T:
        missing_vars = []
        env_vars: Dict[str, Optional[Union[str, int, float, bool]]] = {}

        for f in fields(cls):
            value = os.getenv(f.name.upper())
            if value is None or value.lower() == "none":
                if f.default is MISSING and f.default_factory is MISSING:
                    missing_vars.append(f.name.upper())
                else:
                    value = (
                        f.default if f.default is not MISSING else f.default_factory()
                    )
            else:
                value = cls._convert_type(value, f.type)
            env_vars[f.name] = value

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

        return cls(**env_vars)

    @staticmethod
    def _convert_type(
        value: str, field_type: Union[Type, str]
    ) -> Union[str, int, float, bool, None, Enum]:
        if isinstance(field_type, str):
            field_type = EnvLoader.type_mapping.get(field_type, eval(field_type))

        origin = get_origin(field_type)
        args = get_args(field_type)

        if origin is Union:
            for arg in args:
                try:
                    return EnvLoader._convert_type(value, arg)
                except (ValueError, TypeError):
                    continue
            raise ValueError(f"Cannot convert {value} to any of {args}")

        if isinstance(field_type, type) and issubclass(field_type, Enum):
            try:
                # Try converting directly
                return field_type(value)
            except ValueError:
                # Handle case where value is in form 'EnumClass.EnumMember'
                enum_class, enum_member = value.split(".")
                enum_type = EnvLoader.type_mapping.get(enum_class)
                if enum_type and issubclass(enum_type, Enum):
                    return enum_type[enum_member]

        value = html.unescape(value)
        if field_type == bool:
            return ast.literal_eval(value.capitalize())
        if field_type == int:
            return int(value)
        if field_type == float:
            return float(value)
        if field_type == str:
            return value

        return ast.literal_eval(value)


@dataclass
class GeneralVariables(EnvLoader):
    model_id: str
    model_bazaar_endpoint: str
    model_bazaar_dir: str
    license_key: str
    task_runner_token: str
    type: ModelType = ModelType.NDB
    sub_type: Union[UDTSubType, NDBSubType] = NDBSubType.v1
    llm_provider: str = "openai"
    genai_key: Optional[str] = None

    production: bool = False

    def deployment_permissions(self, token: str):
        deployment_permissions_endpoint = urljoin(
            self.model_bazaar_endpoint,
            f"api/deploy/permissions/{self.model_id}",
        )
        response = requests.get(
            deployment_permissions_endpoint,
            headers={"Authorization": "Bearer " + token},
        )
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            return {
                "read": False,
                "write": False,
                "exp": now() + datetime.timedelta(minutes=5),
                "override": False,
            }
        elif response.status_code != status.HTTP_200_OK:
            print(response.text)
            return {
                "read": False,
                "write": False,
                "exp": now(),
                "override": False,
            }
        res_json = response.json()
        permissions = res_json["data"]
        permissions["exp"] = datetime.datetime.fromisoformat(permissions["exp"])
        return permissions

    def get_nomad_endpoint(self) -> str:
        # Parse the model_bazaar_endpoint to extract scheme and host
        from urllib.parse import urlparse, urlunparse

        parsed_url = urlparse(self.model_bazaar_endpoint)

        # Reconstruct the URL with port 4646
        nomad_netloc = f"{parsed_url.hostname}:4646"

        # Rebuild the URL while keeping the original scheme and hostname
        return urlunparse((parsed_url.scheme, nomad_netloc, "", "", "", ""))

    def get_model_dir(self) -> Path:
        return Path(self.model_bazaar_dir) / "models" / self.model_id

    def get_data_dir(self) -> Path:
        return self.get_model_dir() / "deployments" / "data"


def merge_dataclasses_to_dict(*instances) -> dict:
    result = {}
    for instance in instances:
        result.update(asdict(instance))
    return result
