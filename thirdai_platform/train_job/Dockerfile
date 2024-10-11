FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /app

# Install dependencies before copying the directory so python dependencies are 
# cached even when there are changes in the directory.
COPY train_job/requirements.txt /app/train_job/
RUN python3 -m pip install -r train_job/requirements.txt

COPY platform_common/requirements.txt /app/platform_common/
RUN python3 -m pip install -r platform_common/requirements.txt

COPY train_job/ /app/train_job/

COPY platform_common/ /app/platform_common/