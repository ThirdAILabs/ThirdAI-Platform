from llama_cpp import Llama
import asyncio
import time
import os


# model = Llama(model_path="/home/kartik/gen_ai/ggml_models/llama-7b-q8.gguf", chat_format="llama-2", n_threads=os.getenv("NUM_THREADS", 8), n_ctx=2048)
model = Llama(model_path=os.path.join("/models", os.getenv('MODEL', 'llama-7b-q8.gguf')), chat_format="llama-2", n_threads=int(os.getenv("NUM_THREADS", "8")), n_ctx=2048)

ASSISTANT_INSTRUCTION = (
    "Follow the given instructions as a helpful assistant."
)

def llm_generator(query):
    out = model.create_chat_completion(
        [
            {"role": "system", "content": ASSISTANT_INSTRUCTION},
            {"role": "user", "content": query},
        ], stream=True
    )
    for token in out:
        delta = token['choices'][0]['delta']
        if 'content' in delta:
            word = token['choices'][0]['delta']['content']
            yield f"{word}"