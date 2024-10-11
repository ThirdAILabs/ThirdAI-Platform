FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /app

COPY deployment_job/requirements.txt /app/

RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Install thirdai package separately since this is the dependency that changes
# the most often. This allows the other packages to stay cached.
RUN python3 -m pip install thirdai[neural_db_v2]
RUN python3 -m pip install -U langchain-community

# Copy the deployment_job directory contents into the container at /app/deployment_job
COPY deployment_job/ /app/deployment_job/

# Copy the platform_common directory into the container at /app/platform_common
COPY platform_common/ /app/platform_common/

# Set the default command to run the FastAPI application
CMD ["python3", "deployment_job/server.py"]