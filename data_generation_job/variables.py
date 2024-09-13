import ast
import html
import os
from dataclasses import MISSING, asdict, dataclass, fields
from enum import Enum
from typing import Dict, List, Optional, Type, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel

T = TypeVar("T", bound="EnvLoader")


class DataCategory(str, Enum):
    text = "text"
    token = "token"


class LLMProvider(str, Enum):
    openai = "openai"
    cohere = "cohere"


class EnvLoader:
    type_mapping = {"DataCategory": DataCategory, "LLMProvider": LLMProvider}

    @classmethod
    def load_from_env(cls: Type[T]) -> T:
        """Load environment variables and return an instance of the class."""
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
    ) -> Union[str, int, float, bool, List, Dict, None, Enum]:
        """Convert a string value to the specified field type."""
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
    task_prompt: str
    storage_dir: str
    model_bazaar_endpoint: str
    data_category: DataCategory
    genai_key: str
    llm_provider: LLMProvider = LLMProvider.openai
    test_size: float = 0.05


class Entity(BaseModel):
    name: str
    examples: List[str]
    description: str


class TextGenerationVariables(BaseModel):
    samples_per_label: int
    target_labels: List[Entity]
    user_vocab: Optional[List[str]] = None
    user_prompts: Optional[List[str]] = None
    vocab_per_sentence: int = 4

    def to_dict(self):
        result = self.model_dump()
        result["target_labels"] = self.target_labels
        return result


class TokenGenerationVariables(BaseModel):
    tags: List[Entity]
    num_sentences_to_generate: int
    num_samples_per_tag: Optional[int] = None

    def to_dict(self):
        result = self.model_dump()
        result["tags"] = self.tags
        return result
