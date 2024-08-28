from dotenv import load_dotenv

load_dotenv()

import os
from urllib.parse import urljoin

import requests
import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from llms import OnPremLLM, default_keys, model_classes
from pydantic import BaseModel, ValidationError
from pydantic_models import GenerateArgs

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/llm-dispatch/generate")
async def generate(websocket: WebSocket):
    """
    WebSocket endpoint to generate text using a specified generative AI model.
    Will keep sending content until "end_of_stream" is True.
    If an error is found, "status" will be "error".

    Example:
    1. Client sends:
    ```
    {
        "query": "Tell me a story",
        "model": "gpt-3",
        "provider": "openai",
        "key": "your-api-key"
    }
    ```

    2. Server sends (multiple messages as content is generated):
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
    """
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        try:
            generate_args = GenerateArgs.parse_raw(data)
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

    generated_response = ""
    try:
        async for next_word in llm.stream(
            key=key, query=generate_args.query, model=generate_args.model
        ):
            generated_response += next_word
            await websocket.send_json(
                {"status": "success", "content": next_word, "end_of_stream": False}
            )
    except Exception as e:
        print("Error", e)
        await websocket.send_json(
            {
                "status": "error",
                "detail": "Error while generating content",
                "end_of_stream": True,
            }
        )
    await websocket.send_json(
        {"status": "success", "content": "", "end_of_stream": True}
    )

    if (
        generate_args.original_query is not None
        and generate_args.cache_access_token is not None
    ):
        try:
            res = requests.post(
                urljoin(os.environ["MODEL_BAZAAR_ENDPOINT"], "/cache/insert"),
                params={
                    "query": generate_args.original_query,
                    "llm_res": generated_response,
                },
                headers={
                    "Authorization": f"Bearer {generate_args.cache_access_token}",
                },
            )
            if res.status_code != 200:
                print(f"LLM Cache Insertion failed: {res}")
        except Exception as e:
            print("LLM Cache Insert Error", e)


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
