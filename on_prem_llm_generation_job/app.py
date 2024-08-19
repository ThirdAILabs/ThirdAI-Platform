from typing import AsyncGenerator, NoReturn

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, StreamingResponse
from llm_generator import llm_generator
import asyncio
import threading
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

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

@app.post("/generate")
async def stream_output(body: InputModel):
    await acquire()
    return StreamingResponse(wrapped_generator(body.query))




if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        log_level="debug",
        reload=True,
        workers=1
    )