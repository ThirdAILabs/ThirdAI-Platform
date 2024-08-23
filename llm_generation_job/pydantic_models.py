from typing import Optional

from pydantic import BaseModel


class GenerateArgs(BaseModel):
    query: str
    key: Optional[str] = None
    model: str = "gpt-3.5-turbo"
    provider: str = "openai"

    model_id: Optional[str] = None
    access_token: Optional[str] = None
