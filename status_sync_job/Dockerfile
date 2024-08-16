FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

WORKDIR /app

# Install dependencies before copying the directory so python dependencies are 
# cached even when there are changes in the directory.
COPY requirements.txt /app
RUN pip install -r /app/requirements.txt

COPY . /app

CMD ["python3", "sync_status.py"]
