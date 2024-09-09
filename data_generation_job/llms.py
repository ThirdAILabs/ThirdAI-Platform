import os
from abc import ABC, abstractmethod
from typing import Optional

import cohere
from openai import OpenAI


class LLMBase(ABC):
    @abstractmethod
    def completion(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> str:
        pass


class OpenAILLM(LLMBase):
    def __init__(self, api_key: str):
        super().__init__()
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
            temperature=0.8,
        )

        return response.choices[0].message.content


class CohereLLM(LLMBase):
    def __init__(self, api_key: str):
        super().__init__()
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

        return response.text


llm_classes = {
    "openai": OpenAILLM,
    "cohere": CohereLLM,
}
