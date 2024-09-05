from dotenv import load_dotenv

load_dotenv()

import uvicorn
import os
from urllib.parse import urljoin

import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from llms import default_keys, model_classes
from pydantic import ValidationError
from typing import Optional

from pydantic import BaseModel


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateArgs(BaseModel):
    query: str
    key: Optional[str] = None
    model: str = "gpt-3.5-turbo"
    provider: str = "openai"

    # For caching we want just the query, not the entire prompt.
    original_query: Optional[str] = None
    cache_access_token: Optional[str] = None


@app.websocket("/llm-dispatch/generate")
async def generate(websocket: WebSocket):
    """
    WebSocket endpoint to generate text using a specified generative AI model.
    Will keep sending content until "end_of_stream" is True.
    If an error is found, "status" will be "error".

    Expected Input Message Format:
     ```
     {
         "query": "Your input text",
         "model": "Model name",
         "provider": "AI provider",
         "key": "Optional API key"
     }
     ```

    Example Success:

    Server sends (multiple messages as content is generated):
    ```
    {
        "status": "success",
        "content": "Once upon a time, ",
        "end_of_stream": False
    }
    ...
    {
        "status": "success",
        "content": "they lived happily ever after.",
        "end_of_stream": True
    }
    ```

    Example Error:
     ```
     {
         "status": "error",
         "detail": "No generative AI key provided",
         "end_of_stream": True
     }
     ```

    Providers should be one of on-prem, openai, or cohere
    Other errors include missing genai key, unsupported provider, invalid
    arguments, or internal error
    """
    await websocket.accept()

    while True:
        data = await websocket.receive_text()
        try:
            generate_args = GenerateArgs.parse_raw(data)
            print(f"Received args from client: {data}", flush=True)
            break
        except ValidationError as e:
            await websocket.send_json(
                {
                    "status": "error",
                    "detail": "Invalid arguments",
                    "errors": e.errors(),
                    "end_of_stream": True,
                }
            )
            return
        except Exception as e:
            await websocket.send_json(
                {"status": "error", "detail": "Unexpected error", "end_of_stream": True}
            )
            return

    key = generate_args.key or default_keys.get(generate_args.provider.lower())
    if not key:
        await websocket.send_json(
            {
                "status": "error",
                "detail": "No generative AI key provided",
                "end_of_stream": True,
            }
        )
        return

    llm_class = model_classes.get(generate_args.provider.lower())
    if llm_class is None:
        await websocket.send_json(
            {
                "status": "error",
                "detail": "Unsupported provider",
                "end_of_stream": True,
            }
        )
        return

    llm = llm_class()

    print(f"Starting generation with provider '{generate_args.provider.lower()}':", flush=True)

    generated_response = ""
    try:
        async for next_word in llm.stream(
            key=key, query=generate_args.query, model=generate_args.model
        ):
            generated_response += next_word
            await websocket.send_json(
                {"status": "success", "content": next_word, "end_of_stream": False}
            )
            print(next_word, end ="", flush=True)
    except Exception as e:
        print("Error during generation", e, flush=True)
        await websocket.send_json(
            {
                "status": "error",
                "detail": "Error while generating content",
                "errors": e.errors(),
                "end_of_stream": True,
            }
        )
        return

    print("Completed generation", flush=True)
    await websocket.send_json(
        {"status": "success", "content": "", "end_of_stream": True}
    )

    if (
        generate_args.original_query is not None
        and generate_args.cache_access_token is not None
    ):
        await insert_into_cache(
            generate_args.original_query,
            generated_response,
            generate_args.cache_access_token,
        )


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
            print(f"LLM Cache Insertion failed: {res}", flush=True)
    except Exception as e:
        print("LLM Cache Insert Error", e, flush=True)


@app.get("/llm-dispatch/health")
async def health_check():
    """
    Returns {"status": "healthy"} if successful.
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
