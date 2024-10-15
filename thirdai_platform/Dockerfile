FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /app

# Install PostgreSQL client version 17.x
RUN apt-get update && \
    apt-get install -y wget gnupg2 lsb-release && \
    echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
    apt-get update && \
    apt-get install -y postgresql-client-17

COPY **/requirements.txt /app/

RUN pip install -r /app/recovery_snapshot_job/requirements.txt
RUN pip install -r /app/data_generation_job/requirements.txt
RUN pip install -r /app/llm_cache_job/requirements.txt
RUN pip install -r /app/llm_dispatch_job/requirements.txt
RUN pip install -r /app/train_job/requirements.txt
RUN pip install -r /app/deployment_job/requirements.txt
RUN pip install -r /app/requirements.txt
RUN pip install -r /app/platform_common/requirements.txt

# Install thirdai package separately since this is the dependency that changes
# the most often. This allows the other packages to stay cached.
RUN python3 -m pip install thirdai[neural_db_v2]
RUN python3 -m pip install -U langchain-community

COPY . /app

ARG tag
ARG docker_registry
ARG docker_username
ARG docker_password

ENV TAG $tag
ENV DOCKER_REGISTRY $docker_registry
ENV DOCKER_USERNAME $docker_username
ENV DOCKER_PASSWORD $docker_password
ENV PLATFORM docker

RUN chmod +x ./entrypoint.sh

CMD ["./entrypoint.sh"]