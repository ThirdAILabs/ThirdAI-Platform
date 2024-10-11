FROM python:3.11

WORKDIR /app

COPY data_generation_job/ /app/data_generation_job/

COPY platform_common/ /app/platform_common/

RUN python3 -m pip install -r data_generation_job/requirements.txt

CMD ["python3", "data_generation_job/run.py"]