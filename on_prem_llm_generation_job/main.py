import asyncio

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from llm_generator import llm_generator
from pydantic import BaseModel

app = FastAPI(
    docs_url=f"/on-prem-llm/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

is_processing = False


async def acquire():
    global is_processing
    while is_processing:
        await asyncio.sleep(0.5)
    is_processing = True


def release():
    global is_processing
    is_processing = False


async def wrapped_generator(query):
    try:
        for word in llm_generator(query):
            await asyncio.sleep(0)
            print(word)
            yield word
    except asyncio.CancelledError:
        print("caught cancelled error")
    finally:
        release()


# Define a Pydantic model for the request body
class InputModel(BaseModel):
    query: str


@app.post("/on-prem-llm/generate")
async def stream_output(body: InputModel):
    await acquire()
    return StreamingResponse(wrapped_generator(body.query))


if __name__ == "__main__":
    uvicorn.run(
        "app:app", host="0.0.0.0", port=8000, log_level="debug", reload=True, workers=1
    )
