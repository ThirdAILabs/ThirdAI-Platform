import json
import logging
import math
import os
import re
import socket
from functools import wraps
from pathlib import Path
from urllib.parse import urljoin

import bcrypt
import requests
from database import schema
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from jinja2 import Template
from licensing.verify.verify_license import valid_job_allocation, verify_license
from sqlalchemy.orm import Session

logger = logging.getLogger("ThirdAI_Platform")


def setup_logger(
    level=logging.DEBUG, format="%(asctime)s | [%(name)s] [%(levelname)s] %(message)s"
):
    """
    Set up the logger with the specified logging level and format.

    Parameters:
    - level: Logging level (e.g., logging.DEBUG).
    - format: Logging format string.
    """
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    formatter = logging.Formatter(format)
    console_handler.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(console_handler)

    logger.setLevel(level)
    logger.info("Initialized console logging.")


setup_logger()


def model_bazaar_path():
    return "/model_bazaar" if os.path.exists("/.dockerenv") else os.getenv("SHARE_DIR")


def response(status_code: int, message: str, data={}, success: bool = None):
    """
    Create a JSON response.

    Parameters:
    - status_code: HTTP status code for the response.
    - message: Message to include in the response.
    - data: Optional data to include in the response (default is an empty dictionary).
    - success: Optional boolean indicating success or failure (default is None).

    Returns:
    - JSONResponse: FastAPI JSONResponse object.
    """
    if success is not None:
        status = "success" if success else "failed"
    else:
        status = "success" if status_code < 400 else "failed"
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "message": message, "data": data},
    )


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
        "train_status": result.train_status,
        "deploy_status": result.deploy_status,
        "team_id": str(result.team_id),
        "model_id": str(result.id),
        "sub_type": result.sub_type,
    }

    # Include metadata if it exists
    if result.meta_data:
        metadata = result.meta_data
        if metadata.train:
            # Ensure metadata.train is a dictionary
            if isinstance(metadata.train, str):
                try:
                    metadata.train = json.loads(metadata.train)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON for train: {e}")
                    metadata.train = {}
            info.update(metadata.train)
        if metadata.general:
            # Ensure metadata.general is a dictionary
            if isinstance(metadata.general, str):
                try:
                    metadata.general = json.loads(metadata.general)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON for general: {e}")
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


def get_model(session: Session, username: str, model_name: str):
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
        raise ValueError(str(error))
    model: schema.Model = get_model(
        session, username=model_username, model_name=model_name
    )
    if not model:
        raise ValueError("There is no model with the given name.")
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
        print(f"Job {job_id} stopped successfully")
    else:
        print(
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
        print(
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


def get_empty_port():
    """
    Get an empty port.

    Returns:
    - int: The empty port number.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))  # Bind to an empty
    port = sock.getsockname()[1]
    sock.close()
    return port


def get_expiry_min(size: int):
    """
    This is a helper function to calculate the expiry time for the signed
    url for azure blob, which is required to push a model to model bazaar.
    Taking an average speed of 300 to 400 KB/s we give an extra 60 min for every 1.5GB.
    """
    return 60 * (1 + math.floor(size / 1500))


def list_workflow_models(workflow: schema.Workflow):
    models_info = []
    for workflow_model in workflow.workflow_models:
        model_info = get_high_level_model_info(workflow_model.model)
        model_info["component"] = workflow_model.component  # Append the component info
        models_info.append(model_info)
    return models_info


def get_workflow(session, workflow_id, authenticated_user):
    workflow: schema.Workflow = session.query(schema.Workflow).get(workflow_id)

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found.",
        )

    if (
        workflow.user_id != authenticated_user.user.id
        and not authenticated_user.user.is_global_admin()
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have owner permissions to this workflow",
        )

    return workflow


def save_dict(obj: dict, path: str):
    with open(path, "w") as fp:
        json.dump(obj, fp, indent=4)


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
