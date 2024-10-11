FROM python:3.11

WORKDIR /app

# Install PostgreSQL client version 17.x
RUN apt-get update && \
    apt-get install -y wget gnupg2 lsb-release && \
    echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
    apt-get update && \
    apt-get install -y postgresql-client-17

# Install dependencies before copying the directory so python dependencies are 
# cached even when there are changes in the directory.
COPY ./requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY ./. /app

CMD ["python3", "run.py"]