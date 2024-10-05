import json
import os
from typing import AsyncGenerator, List
from urllib.parse import urljoin

import aiohttp
from utils import Reference, combine_query_and_context


class LLMBase:
    async def stream(
        self, key: str, query: str, prompt: str, references: List[Reference], model: str
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError("Subclasses must implement this method")


class OpenAILLM(LLMBase):
    async def stream(
        self, key: str, query: str, prompt: str, references: List[Reference], model: str
    ) -> AsyncGenerator[str, None]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }
        body = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": combine_query_and_context(
                        query=query, prompt=prompt, references=references
                    ),
                }
            ],
            "stream": True,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body) as response:
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


class CohereLLM(LLMBase):
    async def stream(
        self, key: str, query: str, prompt: str, references: List[Reference], model: str
    ) -> AsyncGenerator[str, None]:
        url = "https://api.cohere.com/v1/chat"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }
        body = {
            "message": query,
            "model": model,
            "chat_history": [
                {
                    "role": "USER",
                    "message": combine_query_and_context(
                        query=query, prompt=prompt, references=references
                    ),
                }
            ],
            "stream": True,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body) as response:
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


class OnPremLLM(LLMBase):
    async def stream(
        self, key: str, query: str, prompt: str, references: List[Reference], model: str
    ) -> AsyncGenerator[str, None]:
        backend_endpoint = os.getenv("MODEL_BAZAAR_ENDPOINT")

        if backend_endpoint is None:
            raise ValueError("Could not read MODEL_BAZAAR_ENDPOINT.")

        url = urljoin(backend_endpoint, "/on-prem-llm/completion")

        headers = {"Content-Type": "application/json"}
        data = {
            "system_prompt": "You are a helpful assistant. Please be concise in your answers.",
            "prompt": combine_query_and_context(
                query=query,
                prompt=prompt,
                references=references,
                reverse_ref_order=True,
            )
            + "<|assistant|>",
            "stream": True,
            # Occasionally the model will repeat itself infinitely, this cuts off
            # the model at 1000 output tokens so that doesn't occur. Alternatively
            # we could increase the repeat_penalty argument but its dependent on
            # the model and there have been reports of output quality being quite
            # sensitive to this. We set it to 1000 because throughput is important
            # and answers aren't super useful past 1000 tokens anyways.
            "n_predict": 1000,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status != 200:
                    raise Exception(
                        f"Failed to connect to On Prem LLM server: {response.status}"
                    )
                async for line in response.content.iter_any():
                    line = line.decode("utf-8").strip()
                    if line and line.startswith("data: "):
                        offset = len("data: ")
                        try:
                            data = json.loads(line[offset:])
                        except:
                            continue
                        if "content" in data:
                            yield data["content"]


model_classes = {
    "openai": OpenAILLM,
    "cohere": CohereLLM,
    "on-prem": OnPremLLM,
}

default_keys = {
    "openai": os.getenv("OPENAI_KEY", ""),
    "cohere": os.getenv("COHERE_KEY", ""),
    "on-prem": "no key",  # TODO(david) add authentication to the service
}
