import json
import logging
import math
import os
import re
import shutil
from collections import defaultdict, deque
from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import bcrypt
import requests
import sqlalchemy as sa
from database import schema
from fastapi import HTTPException, status
from jinja2 import Template
from licensing.verify.verify_license import valid_job_allocation, verify_license
from platform_common.pydantic_models.training import LabelEntity
from platform_common.thirdai_storage import data_types, storage
from sqlalchemy.orm import Session


def model_bazaar_path():
    return "/model_bazaar" if os.path.exists("/.dockerenv") else os.getenv("SHARE_DIR")


def hash_password(password: str):
    """
    Hash a password using bcrypt.

    Parameters:
    - password: The plaintext password to hash.

    Returns:
    - str: The hashed password.
    """
    byte_password = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(byte_password, salt).decode()


def list_all_dependencies(model: schema.Model) -> List[schema.Model]:
    queue = deque()
    queue.append(model)
    visited = set()

    all_models = []

    while len(queue) > 0:
        m: schema.Model = queue.popleft()
        if m.id in visited:
            continue

        visited.add(m.id)

        all_models.append(m)

        queue.extend(dep.dependency for dep in m.dependencies)

    return all_models


def get_job_error(
    session: Session, model_id: str, job_type: str, status: schema.Status
) -> Optional[str]:
    # Return the first error since often later errors may be indirectly caused by
    # the first.
    error = (
        session.query(schema.JobError)
        .filter(
            schema.JobError.model_id == model_id,
            schema.JobError.job_type == job_type,
            schema.JobError.status == status,
        )
        .order_by(sa.asc(schema.JobError.timestamp))
        .first()
    )
    if not error:
        return None
    return error.message


def get_detailed_reasons(
    session: Session,
    job_type: str,
    status: schema.Status,
    reasons: List[Dict[str, str]],
) -> List[str]:
    detailed = []
    for reason in reasons:
        error = get_job_error(
            session=session,
            model_id=reason["model_id"],
            job_type=job_type,
            status=status,
        )
        message = reason["message"]
        if error:
            message += " The following error was detected: " + error

        detailed.append(message)
    return detailed


def get_model_status(
    model: schema.Model, train_status: bool
) -> Tuple[schema.Status, List[Dict[str, str]]]:
    # If the model train/deployment hasn't yet been started, was stopped, or has
    # already failed, then the status of its dependencies is irrelevant.
    status = model.train_status if train_status else model.deploy_status
    if status in [
        schema.Status.not_started,
        schema.Status.stopped,
        schema.Status.failed,
    ]:
        return status, [
            {
                "model_id": model.id,
                "message": f"Workflow {model.name} has status {status.value}.",
            }
        ]

    statuses = defaultdict(list)
    for m in list_all_dependencies(model):
        status = m.train_status if train_status else m.deploy_status
        if m.id == model.id:
            statuses[status].append(
                {
                    "model_id": m.id,
                    "message": f"Workflow {model.name} has status {status.value}.",
                }
            )

        else:
            statuses[status].append(
                {
                    "model_id": m.id,
                    "message": f"The workflow depends on workflow {model.name} which has status {status.value}.",
                }
            )

    status_priority_order = [
        schema.Status.failed,
        schema.Status.not_started,
        schema.Status.stopped,
        schema.Status.starting,
        schema.Status.in_progress,
        schema.Status.complete,
    ]

    for status_type in status_priority_order:
        reasons = statuses[status_type]
        if len(reasons) > 0:
            return status_type, reasons


def get_high_level_model_info(result: schema.Model):
    """
    Get high-level information about a model.

    Parameters:
    - result: The model object.

    Returns:
    - dict: Dictionary containing high-level model information.
    """
    info = {
        "model_name": result.name,
        "publish_date": str(result.published_date),
        "user_email": result.user.email,
        "username": result.user.username,
        "access_level": result.access_level,
        "domain": result.domain,
        "type": result.type,
        "train_status": get_model_status(result, train_status=True)[0],
        "deploy_status": get_model_status(result, train_status=False)[0],
        "team_id": str(result.team_id),
        "model_id": str(result.id),
        "sub_type": result.sub_type,
    }

    info["attributes"] = result.get_attributes()

    info["dependencies"] = [
        {
            "model_id": m.dependency_id,
            "model_name": m.dependency.name,
            "type": m.dependency.type,
            "sub_type": m.dependency.sub_type,
            "username": m.dependency.user.username,
        }
        for m in result.dependencies
    ]

    info["used_by"] = [
        {
            "model_id": m.model_id,
            "model_name": m.model.name,
            "username": m.model.user.username,
        }
        for m in result.used_by
    ]

    # Include metadata if it exists
    if result.meta_data:
        metadata = result.meta_data
        if metadata.train:
            # Ensure metadata.train is a dictionary
            if isinstance(metadata.train, str):
                try:
                    metadata.train = json.loads(metadata.train)
                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding JSON for train: {e}")
                    metadata.train = {}
            info.update(metadata.train)
        if metadata.general:
            # Ensure metadata.general is a dictionary
            if isinstance(metadata.general, str):
                try:
                    metadata.general = json.loads(metadata.general)
                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding JSON for general: {e}")
                    metadata.general = {}
            info.update(metadata.general)

    return info


def validate_name(name):
    """
    Validate a name using a regex pattern.

    Parameters:
    - name: The name to validate.

    Raises:
    - ValueError: If the name is not valid.
    """
    regex_pattern = "^[\w-]+$"
    if not re.match(regex_pattern, name):
        raise ValueError("name is not valid")


def get_model(
    session: Session, username: str, model_name: str
) -> Optional[schema.Model]:
    """
    Get a model by username and model name.

    Parameters:
    - session: SQLAlchemy session.
    - username: Username of the model owner.
    - model_name: Name of the model.

    Returns:
    - schema.Model: The model object if found, otherwise None.
    """
    return (
        session.query(schema.Model)
        .join(schema.User)
        .filter(schema.User.username == username, schema.Model.name == model_name)
        .first()
    )


def parse_model_identifier(model_identifier):
    """
    Parse a model identifier into username and model name.

    Parameters:
    - model_identifier: The model identifier in the format 'username/model_name'.

    Returns:
    - tuple: A tuple containing the username and model name.

    Raises:
    - ValueError: If the model identifier is not valid.
    """
    regex_pattern = "^[\w-]+\/[\w-]+$"
    if re.match(regex_pattern, model_identifier):
        username, model_name = model_identifier.split("/")
        return username, model_name
    else:
        raise ValueError("model identifier is not valid")


def get_model_from_identifier(model_identifier, session):
    """
    Get a model from a model identifier.

    Parameters:
    - model_identifier: The model identifier in the format 'username/model_name'.
    - session: SQLAlchemy session.

    Returns:
    - schema.Model: The model object.

    Raises:
    - ValueError: If there is no model with the given name.
    """
    try:
        model_username, model_name = parse_model_identifier(model_identifier)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to parse model identifier: {error}",
        )
    model: schema.Model = get_model(
        session, username=model_username, model_name=model_name
    )
    if not model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"There is no model with name {model_identifier}.",
        )
    return model


TASK_RUNNER_TOKEN = os.getenv("TASK_RUNNER_TOKEN")


def get_hcl_payload(filepath, is_jinja, **kwargs):
    """
    Get the HCL payload from a file.

    Parameters:
    - filepath: Path to the HCL file.
    - is_jinja: Boolean indicating if the file is a Jinja template.
    - kwargs: Additional keyword arguments to render the Jinja template.

    Returns:
    - dict: Dictionary containing the HCL payload.
    """
    with open(filepath, "r") as file:
        content = file.read()

    if is_jinja:
        template = Template(content, autoescape=True)
        hcl_content = template.render(**kwargs)
    else:
        hcl_content = content

    payload = {"JobHCL": hcl_content, "Canonicalize": True}

    return payload


def nomad_job_exists(job_id, nomad_endpoint):
    """
    Check if a Nomad job exists.

    Parameters:
    - job_id: The ID of the Nomad job.
    - nomad_endpoint: The Nomad endpoint.

    Returns:
    - bool: True if the job exists, otherwise False.
    """
    headers = {"X-Nomad-Token": TASK_RUNNER_TOKEN}
    response = requests.get(
        urljoin(nomad_endpoint, f"v1/job/{job_id}"), headers=headers
    )
    return response.status_code == 200


def get_nomad_job(job_id, nomad_endpoint):
    headers = {"X-Nomad-Token": TASK_RUNNER_TOKEN}
    response = requests.get(
        urljoin(nomad_endpoint, f"v1/job/{job_id}"), headers=headers
    )
    if response.status_code == 200:
        return response.json()

    return None


def submit_nomad_job(filepath, nomad_endpoint, **kwargs):
    """
    Submit a generated HCL job file from a Jinja file to Nomad.

    Parameters:
    - filepath: Path to the HCL or Jinja file.
    - nomad_endpoint: The Nomad endpoint.
    - kwargs: Additional keyword arguments for rendering the Jinja template.

    Returns:
    - Response: The response from the Nomad API.
    """
    json_payload_url = urljoin(nomad_endpoint, "v1/jobs/parse")
    submit_url = urljoin(nomad_endpoint, "v1/jobs")
    headers = {"Content-Type": "application/json", "X-Nomad-Token": TASK_RUNNER_TOKEN}

    filepath_ext = filepath.split(".")[-1]
    is_jinja = filepath_ext == "j2"
    hcl_payload = get_hcl_payload(filepath, is_jinja=is_jinja, **kwargs)

    # Before submitting a job to nomad, we must convert the HCL file to JSON
    json_payload_response = requests.post(
        json_payload_url, headers=headers, json=hcl_payload
    )

    json_payload_response.raise_for_status()

    json_payload = json_payload_response.json()

    # Submit the JSON job spec to Nomad
    response = requests.post(submit_url, headers=headers, json={"Job": json_payload})

    if response.status_code != 200:
        raise requests.exceptions.HTTPError(
            f"Request to nomad service failed. Status code: {response.status_code}, Content: {response.content}"
        )

    return response


def delete_nomad_job(job_id, nomad_endpoint):
    """
    Delete a Nomad job.

    Parameters:
    - job_id: The ID of the Nomad job.
    - nomad_endpoint: The Nomad endpoint.

    Returns:
    - Response: The response from the Nomad API.
    """
    job_url = urljoin(nomad_endpoint, f"v1/job/{job_id}")
    headers = {"X-Nomad-Token": TASK_RUNNER_TOKEN}
    response = requests.delete(job_url, headers=headers)

    if response.status_code == 200:
        logging.info(f"Job {job_id} stopped successfully")
    else:
        logging.error(
            f"Failed to stop job {job_id}. Status code: {response.status_code}, Response: {response.text}"
        )

    return response


def list_services(nomad_endpoint: str):
    headers = {"X-Nomad-Token": TASK_RUNNER_TOKEN}
    return requests.get(urljoin(nomad_endpoint, "v1/services"), headers=headers)


def get_service_info(nomad_endpoint: str, service_name: str):
    headers = {"X-Nomad-Token": TASK_RUNNER_TOKEN}
    return requests.get(
        urljoin(nomad_endpoint, f"v1/service/{service_name}"), headers=headers
    )


def get_job_name(model: schema.Model, job_type: str) -> str:
    if job_type == "train":
        return model.get_train_job_name()
    elif job_type == "deploy":
        return model.get_deployment_name()
    else:
        raise ValueError(
            f"Invalid job_type '{job_type}'. Must be either 'train', 'deploy'."
        )


def get_task(job_type: str) -> str:
    if job_type == "train":
        return "server"
    elif job_type == "deploy":
        return "backend"
    else:
        raise ValueError(
            f"Invalid job_type '{job_type}'. Must be either 'train', 'deploy'."
        )


def get_logs(nomad_endpoint: str, alloc_id: str, task: str, log_type: str) -> str:
    res = requests.get(
        urljoin(nomad_endpoint, f"v1/client/fs/logs/{alloc_id}"),
        headers={"X-Nomad-Token": TASK_RUNNER_TOKEN},
        params={
            "task": task,
            "type": log_type,
            "origin": "end",
            "offset": 5000,
            "plain": True,
        },
    )

    if res.status_code != 200:
        raise ValueError("Error getting logs for job: " + str(res.content))

    _, full_logs = res.content.decode().split("\n", 1)
    return full_logs


def get_job_logs(
    nomad_endpoint: str, model: schema.Model, job_type: str
) -> List[Dict[str, str]]:
    allocations = requests.get(
        urljoin(nomad_endpoint, f"v1/job/{get_job_name(model, job_type)}/allocations"),
        headers={"X-Nomad-Token": TASK_RUNNER_TOKEN},
    )
    if allocations.status_code != 200:
        raise ValueError("Error getting job allocations: " + str(allocations.content))

    logs = []
    for alloc in allocations.json():
        alloc_id = alloc["ID"]

        stdout_log = get_logs(
            nomad_endpoint=nomad_endpoint,
            alloc_id=alloc_id,
            task=get_task(job_type),
            log_type="stdout",
        )
        stderr_log = get_logs(
            nomad_endpoint=nomad_endpoint,
            alloc_id=alloc_id,
            task=get_task(job_type),
            log_type="stderr",
        )
        logs.append({"stdout": stdout_log, "stderr": stderr_log})

    return logs


def get_platform():
    """
    Get the platform identifier.

    Returns:
    - str: The platform identifier (default is 'docker').

    Options:
    - docker: Docker platform.
    - local: Local platform.
    """
    platform = os.getenv("PLATFORM", "docker")
    options = ["docker", "local"]
    if platform not in options:
        logging.warning(
            f"Invalid platform identifier '{platform}'. Options: {options}. Defaulting to docker."
        )
    return platform


def get_python_path():
    """
    Get the Python path based on the platform.

    Returns:
    - str: The Python path.

    Raises:
    - ValueError: If the PYTHON_PATH environment variable is not set for local development.
    """
    python_path = "python3"
    if get_platform() == "local":
        python_path = os.getenv("PYTHON_PATH")
        if not python_path:
            raise ValueError(
                "PYTHON_PATH environment variable is not set for local development."
            )

    return python_path


def get_root_absolute_path():
    """
    Get the absolute path to the root directory.

    Returns:
    - Path: The absolute path to the root directory.
    """
    return Path(__file__).parent.parent.parent.absolute()


def thirdai_platform_dir():
    return str(get_root_absolute_path() / "thirdai_platform")


def update_json(current_json, new_dict):
    """
    Update a JSON object with a new dictionary.

    Parameters:
    - current_json: The current JSON object (as a string).
    - new_dict: The new dictionary to update the JSON object with.

    Returns:
    - str: The updated JSON object (as a string).
    """
    if current_json is None:
        current_dict = {}
    else:
        current_dict = json.loads(current_json)
    current_dict.update(new_dict)
    return json.dumps(current_dict)


def update_json_list(current_list, new_dict):
    """
    Update a JSON list with a new dictionary.

    Parameters:
    - current_list: The current JSON list (as a string).
    - new_dict: The new dictionary to add to the list.

    Returns:
    - str: The updated JSON list (as a string).
    """
    if current_list is None:
        current_list = []
    else:
        current_list = json.loads(current_list)

    current_list.append(new_dict)
    return json.dumps(current_list)


def model_accessible(model: schema.Model, user: schema.User) -> bool:
    """
    Check if a model is accessible to a user.

    Parameters:
    - model: The model object.
    - user: The user object.

    Returns:
    - bool: True if the model is accessible, otherwise False.
    """
    if model.access_level == "private":
        if model.user.id == user.id:
            return True
        return False

    if model.access_level == "protected":
        if model.domain == user.domain:
            return True
        return False

    return True


def get_expiry_min(size: int):
    """
    This is a helper function to calculate the expiry time for the signed
    url for azure blob, which is required to push a model to model bazaar.
    Taking an average speed of 300 to 400 KB/s we give an extra 60 min for every 1.5GB.
    """
    return 60 * (1 + math.floor(size / 1500))


def validate_license_info():
    try:
        license_info = verify_license(
            os.getenv(
                "LICENSE_PATH", "/model_bazaar/license/ndb_enterprise_license.json"
            )
        )
        if not valid_job_allocation(license_info, os.getenv("NOMAD_ENDPOINT")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resource limit reached, cannot allocate new jobs.",
            )
        return license_info
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"License is not valid. {str(e)}",
        )


def handle_exceptions(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            class_name = args[0].__class__.__name__ if args else "UnknownClass"
            method_name = func.__name__
            logging.error(
                f"Error in class '{class_name}', method '{method_name}' "
                f"with arguments {args[1:]}, and keyword arguments {kwargs}. "
                f"Error: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {str(e)}",
            )

    return wrapper


def tags_in_storage(data_storage: storage.DataStorage) -> List[LabelEntity]:
    tag_metadata: data_types.TagMetadata = data_storage.get_metadata(
        "tags_and_status"
    ).data

    tag_status = tag_metadata.tag_status
    tags = [tag_status[tag] for tag in tag_status.keys() if tag != "O"]
    return tags


def copy_data_storage(old_model: schema.Model, new_model: schema.Model):

    old_storage_dir = Path(model_bazaar_path()) / "data" / str(old_model.id)
    new_storage_dir = Path(model_bazaar_path()) / "data" / str(new_model.id)

    os.makedirs(new_storage_dir, exist_ok=True)
    shutil.copy(old_storage_dir / "data_storage.db", new_storage_dir)


def remove_unused_samples(model: schema.Model):
    # remove unused samples from the old storage and rollback metadata to be in a consistent state
    storage_dir = Path(model_bazaar_path()) / "data" / str(model.id)
    data_storage = storage.DataStorage(
        connector=storage.SQLiteConnector(db_path=storage_dir / "data_storage.db")
    )
    data_storage.remove_untrained_samples("ner")
    data_storage.rollback_metadata("tags_and_status")


def retrieve_token_classification_samples_for_generation(
    data_storage: storage.DataStorage,
) -> List[data_types.DataSample]:
    # retrieve all the samples
    samples: List[data_types.DataSample] = data_storage.retrieve_samples(
        name="ner", num_samples=None, user_provided=True
    )
    # only use the samples that we did not generate synthetic data for
    token_classification_samples = [
        sample.data
        for sample in samples
        if sample.status == data_types.SampleStatus.untrained
    ]

    return token_classification_samples


def read_file_from_back(path: str):
    try:
        fp = open(path, "rb")

        # move the cursor to the end of the file
        fp.seek(0, 2)
        current_position = fp.tell()

        line = b""
        while current_position > 0:
            fp.seek(current_position - 1)
            char = fp.read(1)

            if char == b"\n" and line:
                yield line[::-1].decode()
                line = b""
            else:
                line += char

            current_position -= 1

        if line:
            yield line[::-1].decode()

    finally:
        fp.close()


def disk_occupied():
    usage = shutil.disk_usage(model_bazaar_path())

    return usage.free / usage.total
