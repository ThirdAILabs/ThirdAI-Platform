FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /app

# Install dependencies before copying the directory so python dependencies are 
# cached even when there are changes in the directory.
COPY requirements.txt /app
RUN pip install -r /app/requirements.txt

COPY . /app

# Use build args instead of env variables so that we can pass in these variables
# at build time
ARG tag
ARG docker_registry
ARG docker_username
ARG docker_password
ARG export_image_names_command

ENV TAG $tag
ENV DOCKER_REGISTRY $docker_registry
ENV DOCKER_USERNAME $docker_username
ENV DOCKER_PASSWORD $docker_password
ENV PLATFORM docker
ENV EXPORT_IMAGE_NAMES_COMMAND $export_image_names_command

# Use the entrypoint script as the CMD
RUN chmod +x ./entrypoint.sh
CMD ["./entrypoint.sh"]
