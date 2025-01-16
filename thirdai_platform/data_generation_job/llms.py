import os
from abc import ABC, abstractmethod
from pathlib import Path
from threading import Lock
from typing import Optional
from urllib.parse import urljoin

import cohere
import requests
from openai import OpenAI
from platform_common.utils import save_dict


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
        temperature: float = 0.8,
        **kwargs,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,  # TODO (anyone): Choose the temp based on a random distribution
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
        **kwargs,
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


import logging


class SelfHostedLLM(LLMBase):
    def __init__(
        self,
        access_token: str,
        response_file: Optional[Path] = None,
        record_usage_at: Optional[Path] = None,
    ):
        super().__init__(response_file, record_usage_at)

        # Get the endpoint configuration from the backend
        self.backend_endpoint = os.getenv("MODEL_BAZAAR_ENDPOINT")
        response = requests.get(
            urljoin(self.backend_endpoint, "/api/integrations/self-hosted-llm"),
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code != 200:
            raise Exception("Cannot read self-hosted endpoint.")

        data = response.json()["data"]
        self.url = data["endpoint"]  # This should be the full OpenAI-compatible URL
        self.api_key = data["api_key"]

        if self.url is None or self.api_key is None:
            raise Exception(
                "Self-hosted LLM may have been deleted or not configured. Please check the admin dashboard to configure the self-hosted llm"
            )
        self.logger = logging.getLogger(__name__)

    def completion(self, prompt: str, system_prompt: Optional[str] = None, **kwargs):
        try:
            response = requests.post(
                self.url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",  # Added model parameter
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt or "You are a helpful assistant.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
            )

            self.logger.debug(f"Response status code: {response.status_code}")
            if not response.ok:
                self.logger.error(f"Response content: {response.text}")
            response.raise_for_status()

            response_json = response.json()
            return response_json["choices"][0]["message"]["content"]

        except Exception as e:
            self.logger.error(f"Unexpected error during completion: {str(e)}")
            raise


llm_classes = {
    "openai": OpenAILLM,
    "cohere": CohereLLM,
    "self_hosted": SelfHostedLLM,
}


def verify_llm_access(llm_provider: str, access_token: str):
    try:
        if llm_provider == "openai":
            client = OpenAI(api_key=access_token)
            client.models.list()
        elif llm_provider == "cohere":
            client = cohere.Client(api_key=access_token)
            client.models.list()
        elif llm_provider == "self_hosted":
            # Get configuration from backend
            backend_endpoint = os.getenv("MODEL_BAZAAR_ENDPOINT")
            response = requests.get(
                urljoin(backend_endpoint, "/api/integrations/self-hosted-llm"),
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()["data"]
            if not data["endpoint"] or not data["api_key"]:
                return False
        else:
            raise ValueError(f"Invalid LLM provider: {llm_provider}")
    except Exception as e:
        return False

    return True
