from typing import Optional

from pydantic import BaseModel


class GenerateArgs(BaseModel):
    query: str
    key: Optional[str] = None
    model: str = "gpt-3.5-turbo"
    provider: str = "openai"

    # For caching we want just the query, not the entire prompt. 
    original_query: Optional[str] = None 
    cache_access_token: Optional[str] = None
