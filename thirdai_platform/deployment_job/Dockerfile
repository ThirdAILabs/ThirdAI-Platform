FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /app

# Install dependencies before copying the directory so python dependencies are 
# cached even when there are changes in the directory.
COPY deployment_job/requirements.txt /app/deployment_job/
RUN python3 -m pip install -r deployment_job/requirements.txt

COPY platform_common/requirements.txt /app/platform_common/
RUN python3 -m pip install -r platform_common/requirements.txt

# Install thirdai package separately since this is the dependency that changes
# the most often. This allows the other packages to stay cached.
RUN python3 -m pip install thirdai[neural_db_v2]
RUN python3 -m pip install -U langchain-community

COPY deployment_job/ /app/deployment_job/

COPY platform_common/ /app/platform_common/

CMD ["python3", "-m", "uvicorn","main:app","--app-dir", "deployment_job", "--host","0.0.0.0","--port","80"]