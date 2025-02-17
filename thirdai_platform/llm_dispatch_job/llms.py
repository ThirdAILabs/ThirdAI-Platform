import json
import os
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Optional
from urllib.parse import urljoin

import aiohttp
import requests
from anthropic import AsyncAnthropic
from fastapi import HTTPException
from llm_dispatch_job.utils import Reference, make_prompt


class LLMBase(ABC):
    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    async def stream(
        self,
        query: str,
        task_prompt: str,
        references: List[Reference],
        model: Optional[str],
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError("Subclasses must implement this method")


class OpenAIApiLLM(LLMBase):
    def __init__(self, api_key: str, base_url: str, default_model: str):
        super().__init__(api_key)
        self.url = urljoin(base_url, "chat/completions")
        self.default_model = default_model

    async def stream(
        self,
        query: str,
        task_prompt: str,
        references: List[Reference],
        model: Optional[str],
    ) -> AsyncGenerator[str, None]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        system_prompt, user_prompt = make_prompt(query, task_prompt, references)

        body = {
            "model": model or self.default_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, headers=headers, json=body) as response:
                if response.status == 200:
                    async for multi_chunk_bytes, _ in response.content.iter_chunks():
                        for chunk_string in multi_chunk_bytes.decode("utf8").split(
                            "\n"
                        ):
                            if chunk_string == "":
                                continue
                            offset = len(
                                "data: "
                            )  # The chunk responses are prefixed with "data: "
                            try:
                                chunk = json.loads(chunk_string[offset:])
                            except:
                                continue
                            content = (
                                chunk["choices"][0].get("delta", {}).get("content")
                            )
                            if content is not None:
                                yield content


class OpenAILLM(OpenAIApiLLM):
    def __init__(self, api_key: str):
        super().__init__(
            api_key=api_key,
            base_url="https://api.openai.com/v1/",
            default_model="gpt-4o-mini",
        )


class DeepseekLLM(OpenAIApiLLM):
    def __init__(self, api_key: str):
        # Per https://api-docs.deepseek.com deepseek is compatable with any sdk that
        # uses the openai api.
        super().__init__(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1/",
            default_model="deepseek-chat",
        )


class CohereLLM(LLMBase):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.url = "https://api.cohere.com/v1/chat"

    async def stream(
        self,
        query: str,
        task_prompt: str,
        references: List[Reference],
        model: Optional[str],
    ) -> AsyncGenerator[str, None]:
        model = model or "command-r-plus"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        system_prompt, user_prompt = make_prompt(query, task_prompt, references)

        body = {
            "model": model,
            "chat_history": [
                {"role": "SYSTEM", "message": system_prompt},
                {"role": "USER", "message": user_prompt},
            ],
            "stream": True,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, headers=headers, json=body) as response:
                if response.status == 200:
                    async for line in response.content:
                        line = line.decode("utf8").strip()
                        try:
                            chunk = json.loads(line)
                            if chunk.get(
                                "event_type"
                            ) == "text-generation" and not chunk.get("is_finished"):
                                content = chunk.get("text")
                                if content:
                                    yield content
                        except json.JSONDecodeError as e:
                            raise Exception(f"Error decoding JSON response: {e}")
                        except Exception as e:
                            raise Exception(f"Error processing response chunk: {e}")
                else:
                    error_message = await response.text()
                    raise Exception(f"Cohere API request failed: {error_message}")


class AnthropicLLM(LLMBase):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncAnthropic(api_key=api_key)

    async def stream(
        self,
        query: str,
        task_prompt: str,
        references: List[Reference],
        model: Optional[str],
    ) -> AsyncGenerator[str, None]:
        system_prompt, user_prompt = make_prompt(query, task_prompt, references)

        try:
            async with self.client.messages.stream(
                max_tokens=2048,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt},
                ],
                model=model or "claude-3-5-sonnet-20241022",
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        except Exception as e:
            raise Exception(f"Anthropic API request failed: {e}")


DEFAULT_ON_PREM_PROMPT = (
    "given this context, answer the following as succinctly as possible, "
)


class OnPremLLM(LLMBase):
    def __init__(self, api_key: str = None):
        super().__init__(api_key)
        self.backend_endpoint = os.getenv("MODEL_BAZAAR_ENDPOINT")
        if self.backend_endpoint is None:
            raise ValueError("Could not read MODEL_BAZAAR_ENDPOINT.")
        self.url = urljoin(self.backend_endpoint, "/on-prem-llm/v1/chat/completions")

    async def stream(
        self,
        query: str,
        task_prompt: str,
        references: List[Reference],
        model: str,
    ) -> AsyncGenerator[str, None]:
        system_prompt, user_prompt = make_prompt(
            query, task_prompt or DEFAULT_ON_PREM_PROMPT, references
        )

        headers = {"Content-Type": "application/json"}
        data = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,
            # Occasionally the model will repeat itself infinitely, this cuts off
            # the model at 1000 output tokens so that doesn't occur. Alternatively
            # we could increase the repeat_penalty argument but its dependent on
            # the model and there have been reports of output quality being quite
            # sensitive to this. We set it to 1000 because throughput is important
            # and answers aren't super useful past 1000 tokens anyways.
            "n_predict": 1000,
            # Passing in model is just for logging purposes. For some reason
            # llama.cpp returns gpt-3.5-turbo for this value if not specified
            "model": model,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, headers=headers, json=data) as response:
                if response.status != 200:
                    raise Exception(
                        f"Failed to connect to On Prem LLM server: {response.status}"
                    )
                async for line in response.content.iter_any():
                    line = line.decode("utf-8").strip()
                    if line and line.startswith("data: "):
                        line = line[len("data: ") :]
                        if "[DONE]" in line:
                            break
                        data = json.loads(line)
                        yield data["choices"][0]["delta"]["content"]


def get_self_hosted_endpoint(access_token: str):
    backend_endpoint = os.getenv("MODEL_BAZAAR_ENDPOINT")
    response = requests.get(
        urljoin(backend_endpoint, "/api/integrations/self-hosted-llm"),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if response.status_code != 200:
        raise Exception("Cannot read self-hosted endpoint.")
    data = response.json()["data"]

    endpoint = data["endpoint"]
    api_key = data["api_key"]

    if endpoint is None or api_key is None:
        raise Exception(
            "Self-hosted LLM may have been deleted or not configured. Please check the admin dashboard to configure the self-hosted llm"
        )

    return endpoint, api_key


class SelfHostedLLM(OpenAIApiLLM):
    def __init__(self, access_token: str):
        endpoint, api_key = get_self_hosted_endpoint(access_token=access_token)
        super().__init__(
            api_key=api_key, base_url=endpoint, default_model="no model specified"
        )


model_classes = {
    "openai": OpenAILLM,
    "cohere": CohereLLM,
    "on-prem": OnPremLLM,
    "deepseek": DeepseekLLM,
    "anthropic": AnthropicLLM,
}


class LLMFactory:
    @staticmethod
    def create(
        provider: str, api_key: Optional[str], access_token: Optional[str], logger
    ):
        if provider in model_classes:
            if provider != "on-prem" and api_key is None:
                logger.error("No generative AI key provided")
                raise HTTPException(
                    status_code=400, detail="No generative AI key provided"
                )
            return model_classes[provider](api_key=api_key)

        if provider == "self-host":
            if access_token is None:
                raise HTTPException(
                    status_code=401,
                    detail="Unauthorized. Need access token for self-hosted LLM",
                )

            return SelfHostedLLM(access_token=access_token)

        logger.error(f"Unsupported provider '{provider.lower()}'")
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
