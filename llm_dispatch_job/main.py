import lksjnflaku

from dotenv import load_dotenv

load_dotenv()

import asyncio
import logging
import os
from typing import Optional
from urllib.parse import urljoin

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from llms import default_keys, model_classes
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class GenerateArgs(BaseModel):
    query: str
    key: Optional[str] = None
    model: str = "gpt-4o-mini"
    provider: str = "openai"
    workflow_id: Optional[str] = None

    # For caching we want just the query, not the entire prompt.
    original_query: Optional[str] = None
    cache_access_token: Optional[str] = None


@app.post("/llm-dispatch/generate")
async def generate(generate_args: GenerateArgs):
    """
    Generate text using a specified generative AI model, with content streamed in real-time.
    Returns a StreamingResponse with chunks of generated text.

    Parameters:
        - query: str - The input query or prompt for text generation.
        - key: Optional[str] - API key for the provider.
        - model: str - The model to use for text generation (default: "gpt-4o-mini").
        - provider: str - The AI provider to use (default: "openai"). Providers should be one of on-prem, openai, or cohere
        - workflow_id: Optional[str] - Workflow ID for tracking the request.
        - original_query: Optional[str] - The original query to be cached, used for cache lookup.
        - cache_access_token: Optional[str] - Authorization token for caching responses.

    Returns:
    - StreamingResponse: A stream of generated text in chunks.

    Example Request Body:
    ```
    {
        "query": "Explain the theory of relativity",
        "model": "gpt-4o-mini",
        "provider": "openai",
        "workflow_id": "12345",
        "original_query": "Explain relativity",
        "cache_access_token": "cache_token_abc"
    }
    ```

    Errors:
    - HTTP 400:
        - No API key provided and no default key found for the provider.
        - Unsupported provider.
    - HTTP 500:
        - Error during the text generation process.

    Caching:
    - If `original_query` and `cache_access_token` are provided, the generated content will be cached after completion.
    """

    key = generate_args.key or default_keys.get(generate_args.provider.lower())
    if not key:
        raise HTTPException(status_code=400, detail="No generative AI key provided")

    llm_class = model_classes.get(generate_args.provider.lower())
    if llm_class is None:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    logging.info(
        f"Received request from workflow: '{generate_args.workflow_id}'. "
        f"Starting generation with provider '{generate_args.provider.lower()}':",
    )

    llm = llm_class()

    async def generate_stream():
        generated_response = ""
        try:
            async for next_word in llm.stream(
                key=key, query=generate_args.query, model=generate_args.model
            ):
                generated_response += next_word
                yield next_word
                await asyncio.sleep(0)
            logging.info(
                f"\nCompleted generation for workflow '{generate_args.workflow_id}'.",
            )
        except Exception as e:
            logging.error(f"Error during generation: {e}")
            raise HTTPException(
                status_code=500, detail=f"Error while generating content: {e}"
            )
        else:
            if (
                generate_args.original_query is not None
                and generate_args.cache_access_token is not None
            ):
                await insert_into_cache(
                    generate_args.original_query,
                    generated_response,
                    generate_args.cache_access_token,
                )

    return StreamingResponse(generate_stream(), media_type="text/plain")


async def insert_into_cache(
    original_query: str, generated_response: str, cache_access_token: str
):
    try:
        res = requests.post(
            urljoin(os.environ["MODEL_BAZAAR_ENDPOINT"], "/cache/insert"),
            params={
                "query": original_query,
                "llm_res": generated_response,
            },
            headers={
                "Authorization": f"Bearer {cache_access_token}",
            },
        )
        if res.status_code != 200:
            logging.error(f"LLM Cache Insertion failed: {res}")
    except Exception as e:
        logging.error("LLM Cache Insert Error", e)


@app.get("/llm-dispatch/health")
async def health_check():
    """
    Returns {"status": "healthy"} if successful.
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)
