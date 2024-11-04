import logging
import traceback
from pathlib import Path

from dotenv import load_dotenv
from platform_common.logging import setup_logger

load_dotenv()

import asyncio
import os
from urllib.parse import urljoin

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from llm_dispatch_job.llms import LLMBase, default_keys, model_classes
from llm_dispatch_job.utils import GenerateArgs

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model_bazaar_dir = os.getenv("MODEL_BAZAAR_DIR")
log_dir: Path = Path(model_bazaar_dir) / "logs"

setup_logger(log_dir=log_dir, log_prefix="llm_generation")
logger = logging.getLogger("llm_generation")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)

    logger.info(
        f"Request: {request.method}; URl: {request.url} - {response.status_code}"
    )

    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the traceback
    error_trace = traceback.format_exc()
    logger.error(f"Exception occurred: {error_trace}")

    # Return the exact exception message in the response
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


@app.post("/llm-dispatch/generate")
async def generate(generate_args: GenerateArgs):
    """
    Generate text using a specified generative AI model, with content streamed in real-time.
    Returns a StreamingResponse with chunks of generated text.

    Parameters:
        - query: str - The input query or prompt for text generation.
        - task_prompt: Optional[str] - Additional prompt to guide the generation.
        - references: List[Reference] - List of reference texts with optional sources and metadata.
        - key: Optional[str] - API key for the provider.
        - model: str - The model to use for text generation (default: "gpt-4o-mini").
        - provider: str - The AI provider to use (default: "openai"). Providers should be one of on-prem, openai, or cohere
        - workflow_id: Optional[str] - Workflow ID for tracking the request.
        - cache_access_token: Optional[str] - Authorization token for caching responses.

    Returns:
    - StreamingResponse: A stream of generated text in chunks.

    Example Request Body:
    ```
    {
        "query": "Explain the theory of relativity",
        "task_prompt": "Provide a simple explanation suitable for a high school student.",
        "references": [
            {
                "text": "E = mc^2 is the most famous equation in physics.",
                "source": "Introduction to Physics, 2022",
                "metadata": {"relevance": 0.9}
            }
        ],
        "model": "gpt-4o-mini",
        "provider": "openai",
        "workflow_id": "12345",
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
        logger.error("No generative AI key provided")
        raise HTTPException(status_code=400, detail="No generative AI key provided")

    llm_class = model_classes.get(generate_args.provider.lower())
    if llm_class is None:
        logger.error(f"Unsupported provider '{generate_args.provider.lower()}'")
        raise HTTPException(status_code=400, detail="Unsupported provider")

    logger.info(
        f"Received request from workflow: '{generate_args.workflow_id}'. "
        f"Starting generation with provider '{generate_args.provider.lower()}':",
    )

    llm: LLMBase = llm_class()

    async def generate_stream():
        generated_response = ""
        try:
            async for next_word in llm.stream(
                key=key,
                query=generate_args.query,
                task_prompt=generate_args.task_prompt,
                references=generate_args.references,
                model=generate_args.model,
            ):
                generated_response += next_word
                yield next_word
                await asyncio.sleep(0)
            logger.info(
                f"\nCompleted generation for workflow '{generate_args.workflow_id}'.",
            )
        except Exception as e:
            logger.error(f"Error during generation: {e}")
            raise HTTPException(
                status_code=500, detail=f"Error while generating content: {e}"
            )
        else:
            if generate_args.cache_access_token is not None:
                await insert_into_cache(
                    generate_args.query,
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
            logger.error(
                f"LLM Cache Insertion failed with status {res.status_code}: {res.text}"
            )
    except Exception as e:
        logger.error("LLM Cache Insert Error", e)


@app.get("/llm-dispatch/health")
async def health_check():
    """
    Returns {"status": "healthy"} if successful.
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting LLM generation service...")
    uvicorn.run(app, host="localhost", port=8000, log_level="info")
