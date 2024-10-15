FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /app

# Install dependencies before copying the directory so python dependencies are 
# cached even when there are changes in the directory.
COPY llm_cache_job/requirements.txt /app/llm_cache_job/
RUN python3 -m pip install -r llm_cache_job/requirements.txt

COPY llm_cache_job/ /app/llm_cache_job/

CMD ["python3", "-m", "uvicorn","main:app","--app-dir", "llm_cache_job", "--host","0.0.0.0","--port","80"]