from __future__ import annotations

import ast
import html
import os
from dataclasses import MISSING, dataclass, fields
from typing import Dict, Optional, Type, TypeVar, Union

T = TypeVar("T", bound="EnvLoader")


class EnvLoader:
    @classmethod
    def load_from_env(cls: Type[T]) -> T:
        """Load environment variables and return an instance of the class."""
        missing_vars = []
        env_vars: Dict[str, Optional[str]] = {}

        for f in fields(cls):
            value = os.getenv(f.name.upper())
            if value is None or value.lower() == "none":
                if f.default is MISSING and f.default_factory is MISSING:
                    missing_vars.append(f.name.upper())
                else:
                    value = (
                        f.default if f.default is not MISSING else f.default_factory()
                    )
            env_vars[f.name] = value

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

        return cls(**env_vars)


@dataclass
class GeneralVariables(EnvLoader):
    model_bazaar_endpoint: str
    management_token: str
    promfile: str
    platform: str
