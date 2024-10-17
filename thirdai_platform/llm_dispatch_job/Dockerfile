FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /app

# Install dependencies before copying the directory so python dependencies are 
# cached even when there are changes in the directory.
COPY llm_dispatch_job/requirements.txt /app/llm_dispatch_job/
RUN python3 -m pip install -r llm_dispatch_job/requirements.txt

COPY llm_dispatch_job/ /app/llm_dispatch_job/

CMD ["python3", "-m", "uvicorn","main:app","--app-dir", "llm_dispatch_job", "--host","0.0.0.0","--port","80"]