import os

from llama_cpp import Llama

model = Llama(model_path="/Users/david/Documents/ThirdAI-Platform/on_prem_llm_generation_job/models/Phi-3-mini-4k-instruct-q4.gguf", chat_format="llama-2", n_threads=int(os.getenv("NUM_THREADS", "8")), n_ctx=2048)
# model = Llama(
#     model_path=os.path.join("/models", "Phi-3-mini-4k-instruct-q4.gguf"),
#     chat_format="llama-2",
#     n_threads=int(os.getenv("NUM_THREADS", "8")),
#     n_ctx=2048,
# )

ASSISTANT_INSTRUCTION = "Follow the given instructions (if possible) as a helpful assistant."


def llm_generator(query):
    out = model.create_chat_completion(
        [
            {"role": "system", "content": ASSISTANT_INSTRUCTION},
            {"role": "user", "content": query},
        ],
        stream=True,
    )
    for token in out:
        delta = token["choices"][0]["delta"]
        if "content" in delta:
            word = token["choices"][0]["delta"]["content"]
            yield f"{word}"
