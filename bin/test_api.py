#curl --request POST     --url http://localhost:80/on-prem-llm/completion     --header "Content-Type: application/json"     --data '{"system_prompt": "You are a helpful assistant. Please be concise in your answers.", "prompt": "Are these the same institution?: \n \"Pathology and Histology core at Baylor College of Medicine, Houston, Texas\" and \"Institute of Radiation and Radiation Medicine or Institute of Electromagnetic and Particle Radiation Medicine\" <|assistant|>", "stream": true}'

import requests

url = "http://127.0.0.1:80/on-prem-llm/completion"
headers = {
    "Content-Type": "application/json"
}
data = {
    "system_prompt": "You are a helpful assistant. Please be concise in your answers.",
    "prompt": "Hello my name is david. <|assistant|>",
    "stream": True
}

response = requests.post(url, headers=headers, json=data)

print(response.text)

with requests.post(url, headers=headers, json=data, stream=True) as response:
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            print(chunk.decode('utf-8'))


# curl --request POST --url http://localhost:80/cloud-llm/genpost --header "Content-Type: application/json" --data '{"query": "Hello!"}'


import aiohttp
import json
import asyncio

async def query_llm(query):
    url = "http://127.0.0.1:80/on-prem-llm/completion"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "system_prompt": "You are a helpful assistant. Please be concise in your answers.",
        "prompt": f"{query} <|assistant|>",
        "stream": True
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            async for chunk in response.content.iter_any():
                if chunk:
                    yield chunk.decode('utf-8')

async def main():
    query = "Hello, my name is David."
    async for chunk in query_llm(query):
        print(chunk, end='', flush=True)

asyncio.run(main())






import requests

url = "http://127.0.0.1:80/cloud-llm/genpost"
headers = {
    "Content-Type": "application/json"
}
data = {
    "query": "Hello!",
}

response = requests.post(url, headers=headers, json=data)

print(response.text)

with requests.post(url, headers=headers, json=data, stream=True) as response:
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            print(chunk.decode('utf-8'))