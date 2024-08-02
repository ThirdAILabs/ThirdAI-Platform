from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from llms import default_keys, model_classes
from pydantic import ValidationError
from pydantic_models import GenerateArgs

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/generate")
async def generate(websocket: WebSocket):
    """
    WebSocket endpoint to generate text using a specified generative AI model.

    Parameters:
    - WebSocket connection.

    Expected Message Format:
    ```
    {
        "query": "Your input text",
        "model": "Model name",
        "provider": "AI provider",
        "key": "Optional API key"
    }
    ```

    Response Messages:
    - Success message with generated content:
    ```
    {
        "status": "success",
        "content": "Generated text",
        "end_of_stream": False
    }
    ```
    - Error message in case of invalid arguments:
    ```
    {
        "status": "error",
        "detail": "Invalid arguments",
        "errors": [{"loc": ["field"], "msg": "Error message", "type": "error type"}],
        "end_of_stream": True
    }
    ```
    - Error message in case of missing API key:
    ```
    {
        "status": "error",
        "detail": "No generative AI key provided",
        "end_of_stream": True
    }
    ```
    - Error message in case of unsupported provider:
    ```
    {
        "status": "error",
        "detail": "Unsupported provider",
        "end_of_stream": True
    }
    ```
    - Error message in case of an unexpected error:
    ```
    {
        "status": "error",
        "detail": "Unexpected error",
        "end_of_stream": True
    }
    ```

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

    try:
        async for next_word in llm.stream(
            key=key, query=generate_args.query, model=generate_args.model
        ):
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)
