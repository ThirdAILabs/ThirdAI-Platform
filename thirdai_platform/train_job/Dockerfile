FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /app

COPY train_job/requirements.txt /app/

RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY train_job/ /app/train_job/

COPY platform_common/ /app/platform_common/

CMD ["python3", "train_job/run.py"]