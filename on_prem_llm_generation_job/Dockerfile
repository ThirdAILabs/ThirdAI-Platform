FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

WORKDIR /app

# Install dependencies before copying the directory so python dependencies are 
# cached even when there are changes in the directory.
COPY ./requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY ./. /app/

# TODO if we really want the distribution to be smaller we can download the model at startup
# from https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/tree/main
# download Phi-3-mini-4k-instruct-q4.gguf
COPY ./models /app/models

CMD ["uvicorn","main:app","--reload","--host","0.0.0.0","--port","80"]