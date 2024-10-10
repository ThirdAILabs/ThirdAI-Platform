from abc import ABC, abstractmethod
from pathlib import Path
from threading import Lock
from typing import Optional

import cohere
from openai import OpenAI
from utils import save_dict


class LLMBase(ABC):
    def __init__(
        self,
        response_file: Optional[Path] = None,
        record_usage_at: Optional[Path] = None,
    ):
        self.response_file = response_file
        self.usage_file = record_usage_at
        self.usage = dict()
        self.lock = Lock()

    @abstractmethod
    def completion(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> str:
        pass


class OpenAILLM(LLMBase):
    def __init__(
        self,
        api_key: str,
        response_file: Optional[Path] = None,
        record_usage_at: Optional[Path] = None,
    ):
        super().__init__(response_file, record_usage_at)
        self.client = OpenAI(api_key=api_key)

    def completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model_name: str = "gpt-4o",
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.8,  # TODO (anyone): Choose the temp based on a random distribution
        )

        res = response.choices[0].message.content
        current_usage = dict(response.usage)
        if self.response_file:
            with self.lock:
                with open(self.response_file, "a") as fp:
                    fp.write(f"Prompt: \n{prompt}\n")
                    fp.write(f"Response: \n{res}\n")
                    fp.write(f"\nUsage: \n{current_usage}\n")
                    fp.write("=" * 100 + "\n\n")

        # updating the llm usage
        if self.usage_file:
            with self.lock:
                if model_name not in self.usage:
                    self.usage[model_name] = {}

                for key in ["completion_tokens", "prompt_tokens", "total_tokens"]:
                    self.usage[model_name][key] = (
                        self.usage[model_name].get(key, 0) + current_usage[key]
                    )

                save_dict(self.usage_file, **self.usage)

        return res


class CohereLLM(LLMBase):
    def __init__(
        self,
        api_key: str,
        response_file: Optional[str] = None,
        record_usage_at: Optional[str] = None,
    ):
        super().__init__(response_file, record_usage_at)
        self.client = cohere.Client(api_key=api_key)

    def completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model_name: str = "command-r-plus",
    ) -> str:
        message = ""
        if system_prompt:
            message = f"{system_prompt}\n\n"
        message += prompt

        response = self.client.chat(model=model_name, message=message)

        if self.response_file:
            with self.lock:
                with open(self.response_file, "a") as fp:
                    fp.write(f"Prompt: \n{prompt}\n")
                    fp.write(f"Response: \n{response.text}\n")
                    fp.write("=" * 100 + "\n\n")

        return response.text


llm_classes = {
    "openai": OpenAILLM,
    "cohere": CohereLLM,
}
