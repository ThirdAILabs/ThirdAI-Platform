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
COPY recovery_snapshot_job/requirements.txt /app/recovery_snapshot_job/requirements.txt
RUN pip install -r recovery_snapshot_job/requirements.txt

COPY platform_common/requirements.txt /app/platform_common/
RUN python3 -m pip install -r platform_common/requirements.txt

COPY recovery_snapshot_job/ /app/recovery_snapshot_job/

COPY platform_common/ /app/platform_common/

CMD ["python3", "-m", "recovery_snapshot_job.run"]