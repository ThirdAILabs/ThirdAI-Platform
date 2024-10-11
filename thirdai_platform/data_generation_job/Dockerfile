FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /app

# Install dependencies before copying the directory so python dependencies are 
# cached even when there are changes in the directory.
COPY data_generation_job/requirements.txt /app/data_generation_job/
RUN python3 -m pip install -r data_generation_job/requirements.txt

COPY platform_common/requirements.txt /app/platform_common/
RUN python3 -m pip install -r platform_common/requirements.txt

COPY data_generation_job/ /app/data_generation_job/

COPY platform_common/ /app/platform_common/

CMD ["python3", "-m", "data_generation_job.run"]