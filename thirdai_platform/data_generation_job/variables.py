import ast
import html
import os
from collections import defaultdict
from dataclasses import MISSING, dataclass, fields
from enum import Enum
from typing import Dict, List, Optional, Type, TypeVar, Union, get_args, get_origin

from platform_common.pii.udt_common_patterns import find_common_pattern
from pydantic import BaseModel, Field, field_validator

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
    data_id: str
    storage_dir: str
    model_bazaar_endpoint: str
    data_category: DataCategory
    genai_key: str
    secret_token: str
    llm_provider: LLMProvider = LLMProvider.openai
    test_size: float = 0.05


class EntityStatus(str, Enum):
    trained = "trained"  # if the model has already been trained on the label
    uninserted = "uninserted"  # if label is scheduled to be added to the model

    untrained = "untrained"  # if the label is present in the model but not trained


class Entity(BaseModel):
    name: str
    examples: List[str] = Field(default_factory=list)
    description: str = Field(default="NA")
    status: EntityStatus = EntityStatus.untrained

    @field_validator("name", mode="after")
    def uppercase_name(cls, v):
        return v.upper()


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


class NERSample(BaseModel):
    tokens: List[str]
    tags: List[str]

    def get_example_template(self) -> str:
        # templatizes the sample for passing to LLM
        # Example -> My name is [NAME]
        example = []

        for index, (token, tag) in enumerate(zip(self.tokens, self.tags)):
            if tag == "O":
                example.append(token)
            elif index + 1 == len(self.tokens) or tag != self.tags[index + 1]:
                example.append(f"[{tag}]")

        return " ".join(example)

    def get_tags(self) -> set:
        # returns all the unique non-default tags in the LLM
        return set([tag for tag in self.tags if tag != "O"])

    def get_values(self) -> dict:
        # returns a map of tag to values present for the tag.
        # concatenates consecutive tokens with the same tag into a single value.

        examples = defaultdict(list)
        past_tokens = []

        for index, (token, tag) in enumerate(zip(self.tokens, self.tags)):
            if index + 1 >= len(self.tokens) or tag != self.tags[index + 1]:
                past_tokens.append(token)
                if tag != "O":
                    examples[tag].append(" ".join(past_tokens))

                past_tokens = []

            else:
                past_tokens.append(token)

        return examples


class TokenGenerationVariables(BaseModel):
    tags: List[Entity]
    num_sentences_to_generate: int
    num_samples_per_tag: Optional[int] = None
    # example NER samples
    samples: Optional[List[NERSample]] = None
    templates_per_sample: int = 10

    def to_dict(self):
        result = self.model_dump()
        result["tags"] = self.tags
        result["samples"] = self.samples
        return result

    def remove_common_patterns(self):
        self.tags = [tag for tag in self.tags if find_common_pattern(tag.name) is None]

    def find_common_patterns(self):
        return [tag.name for tag in self.tags if find_common_pattern(tag.name)]
