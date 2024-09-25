import json
import os
import re
import sys
import warnings
from typing import Callable, Dict, List, Optional, Type
from urllib.parse import urljoin

import boto3
import requests
from botocore import UNSIGNED
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from thirdai import neural_db as ndb

from headless.configs import Config


def get_csv_source_id(
    file: str,
    CSV_ID_COLUMN: Optional[str] = None,
    CSV_STRONG_COLUMNS: Optional[List[str]] = None,
    CSV_WEAK_COLUMNS: Optional[List[str]] = None,
    CSV_REFERENCE_COLUMNS: Optional[List[str]] = None,
    CSV_METADATA: Optional[Dict[str, str]] = None,
) -> str:
    """
    Returns the source ID for a CSV file.

    Parameters:
    file (str): Path to the CSV file.
    CSV_ID_COLUMN (str, optional): Column name for IDs.
    CSV_STRONG_COLUMNS (list[str], optional): List of strong columns.
    CSV_WEAK_COLUMNS (list[str], optional): List of weak columns.
    CSV_REFERENCE_COLUMNS (list[str], optional): List of reference columns.
    CSV_METADATA (dict[str, str], optional): Metadata for the CSV file.

    Returns:
    str: The hash ID of the CSV source.

    Raises:
    TypeError: If the file type is not supported.
    """
    _, ext = os.path.splitext(file)

    if ext == ".csv":
        return ndb.CSV(
            file,
            id_column=CSV_ID_COLUMN,
            strong_columns=CSV_STRONG_COLUMNS,
            weak_columns=CSV_WEAK_COLUMNS,
            reference_columns=CSV_REFERENCE_COLUMNS,
            metadata=CSV_METADATA,
        ).hash
    else:
        raise TypeError(f"{ext} Document type isn't supported.")


def get_configs(config_type: type, config_regex: str) -> List[Config]:
    """
    Retrieves a list of configuration subclasses that match a given regex pattern.

    Parameters:
    config_type (type): The base configuration class type.
    config_regex (str): Regular expression to filter configuration names.

    Returns:
    list[Config]: List of matching configuration subclasses.

    Raises:
    Warning: If no configurations match the regex pattern.
    """
    configs = [config for config in config_type.__subclasses__()]
    config_re = re.compile(config_regex)
    configs = list(
        filter(
            lambda config: config.name is not None and config_re.match(config.name),
            configs,
        )
    )
    if len(configs) == 0:
        warnings.warn(
            f"Couldn't match regular expression '{config_regex}' to any configs"
        )

    return configs


def extract_static_methods(cls: Type) -> Dict[str, Callable]:
    """
    Extracts all static methods from a given class and returns them in a dictionary.

    Args:
        cls (Type): The class to extract static methods from.

    Returns:
        Dict[str, Callable]: A dictionary with method names as keys and static methods as values.
    """
    static_methods = {}
    for name, method in cls.__dict__.items():
        if isinstance(method, staticmethod):
            static_methods[name] = method.__func__
    return static_methods


def download_from_s3_if_not_exists(s3_uri, local_dir):
    from botocore.client import Config

    if not os.path.exists(local_dir):
        os.makedirs(local_dir)

    config = Config(
        signature_version=UNSIGNED,
        retries={"max_attempts": 10, "mode": "standard"},
        connect_timeout=5,
        read_timeout=60,
    )

    s3 = boto3.client("s3", config=config)
    bucket_name = s3_uri.split("/")[2]
    s3_path = "/".join(s3_uri.split("/")[3:])

    try:
        for key in s3.list_objects_v2(Bucket=bucket_name, Prefix=s3_path)["Contents"]:
            local_file_path = os.path.join(local_dir, key["Key"].split("/")[-1])
            if not os.path.exists(local_file_path):
                s3.download_file(bucket_name, key["Key"], local_file_path)
                print(f"Downloaded {local_file_path}")
    except (NoCredentialsError, PartialCredentialsError) as e:
        print(f"Error in downloading from S3: {str(e)}")
        sys.exit(1)


def normalize_s3_uri(s3_uri):
    return s3_uri.rstrip("/")


def read_access_token():
    task_runner_token_path = os.path.join(
        "/opt/thirdai_platform/nomad_data/", "task_runner_token.txt"
    )
    try:
        # Open the token file for reading
        with open(task_runner_token_path, "r") as file:
            # Read the entire file contents
            file_contents = file.read()

            # Use regex to find the Secret ID value
            secret_id_match = re.search(r"Secret ID\s*=\s*([^\n]+)", file_contents)

            if secret_id_match:
                # Extract the Secret ID value from the regex match
                secret_id = secret_id_match.group(1).strip()
                return secret_id

    except FileNotFoundError:
        print(f"Error: File '{task_runner_token_path}' not found.")
    except Exception as e:
        print(f"Error reading file '{task_runner_token_path}': {e}")

    return None


TASK_RUNNER_TOKEN = os.getenv("TASK_RUNNER_TOKEN", read_access_token())


def restart_nomad_job(nomad_endpoint, payload):
    submit_url = urljoin(nomad_endpoint, "v1/jobs")
    headers = {"Content-Type": "application/json", "X-Nomad-Token": TASK_RUNNER_TOKEN}
    response = requests.post(submit_url, headers=headers, json={"Job": payload})
    return response


def stop_nomad_job(job_id, nomad_endpoint):
    job_url = urljoin(nomad_endpoint, f"v1/job/{job_id}")
    headers = {"X-Nomad-Token": TASK_RUNNER_TOKEN}
    response = requests.delete(job_url, headers=headers)

    if response.status_code == 200:
        print(f"Job {job_id} stopped successfully")
    else:
        print(
            f"Failed to stop job {job_id}. Status code: {response.status_code}, Response: {response.text}"
        )

    return response


def fetch_job_definition(job_id, nomad_endpoint):
    job_url = urljoin(nomad_endpoint, f"v1/job/{job_id}")
    headers = {"X-Nomad-Token": TASK_RUNNER_TOKEN}
    response = requests.get(job_url, headers=headers)
    if response.status_code != 200:
        print(response.content)
        raise Exception()
    return json.loads(response.content)


def get_nomad_endpoint(input_url):
    # Define a regex pattern to match an IP address, hostname, or 'localhost' with an optional port number
    ip_hostname_pattern = (
        r"(localhost|(?:\d{1,3}\.){3}\d{1,3}|(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})(:\d+)?"
    )

    # Find the first IP address, hostname, or 'localhost' with an optional port number in the input URL
    match = re.search(ip_hostname_pattern, input_url)
    if match:
        # Extract the IP address, hostname, or 'localhost'
        url_part = match.group(1)  # IP address, hostname, or 'localhost'

        # Remove the port number and append ":4646" to the IP address, hostname, or 'localhost'
        modified_url = "http://" + url_part + ":4646/"
        return modified_url
    else:
        # If no IP address, hostname, or 'localhost' is found, return the original URL
        return input_url


def update_docker_image_version(job_definition, new_version):
    """
    Updates the Docker image version in the Nomad job definition.

    Args:
        job_definition (dict): The Nomad job definition.
        new_version (str): The new version of the Docker image (without the 'v' prefix).

    Returns:
        dict: Updated job definition with the new Docker image version.
    """
    # Ensure the new version is prefixed with 'v'
    version_tag = f"v{new_version}"

    # Find the task group and task with the Docker config
    for task_group in job_definition.get("TaskGroups", []):
        for task in task_group.get("Tasks", []):
            if task.get("Driver") == "docker":
                current_image = task["Config"]["image"]
                # Extract base image name without version
                image_name = current_image.split(":")[0]
                # Update the image with the new version
                task["Config"]["image"] = f"{image_name}:{version_tag}"
                print(f"Updated Docker image to: {task['Config']['image']}")

    return job_definition
