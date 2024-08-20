import json
import logging
import math
import os
import re
import socket
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin

import bcrypt
import requests
from database import schema
from fastapi.responses import JSONResponse
from jinja2 import Template
from pydantic import BaseModel, Field, root_validator
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


class UDTExtraOptions(BaseModel):
    """
    Model for User Defined Type (UDT) extra options.

    Attributes:
    - allocation_cores: Optional number of cores to allocate.
    - allocation_memory: Optional amount of memory to allocate.
    - sub_type: Optional subtype of the UDT.
    - target_labels: List of target labels.
    - source_column: Optional source column name.
    - target_column: Optional target column name.
    - default_tag: Optional default tag.
    - delimiter: Optional delimiter (default is ',').
    - text_column: Optional text column name (default is 'text').
    - label_column: Optional label column name (default is 'label').
    - n_target_classes: Optional number of target classes.

    Validators:
    - set_fields_based_on_type: Sets default values based on the subtype.
    """

    allocation_cores: Optional[int] = None
    allocation_memory: Optional[int] = None

    sub_type: Optional[str] = None
    target_labels: List[str] = None
    source_column: Optional[str] = None
    target_column: Optional[str] = None
    default_tag: Optional[str] = None
    delimiter: Optional[str] = None
    text_column: Optional[str] = None
    label_column: Optional[str] = None
    n_target_classes: Optional[int] = None

    @root_validator(pre=True)
    def set_fields_based_on_type(cls, values):
        sub_type = values.get("sub_type")
        if sub_type == "text":
            values["delimiter"] = values.get("delimiter", ",")
            values["text_column"] = values.get("text_column", "text")
            values["label_column"] = values.get("label_column", "label")
            values["n_target_classes"] = values.get("n_target_classes", None)
        elif sub_type == "token":
            values["target_labels"] = values.get("target_labels", [])
            values["source_column"] = values.get("source_column", "source")
            values["target_column"] = values.get("target_column", "target")
            values["default_tag"] = values.get("default_tag", "O")
        return values


class NDBExtraOptions(BaseModel):
    """
    Model for Neural Database (NDB) extra options.

    Attributes:
    - num_models_per_shard: Optional number of models per shard (default is 1).
    - num_shards: Optional number of shards (default is 1).
    - allocation_cores: Optional number of cores to allocate.
    - allocation_memory: Optional amount of memory to allocate.
    - model_cores: Optional number of cores for the model.
    - model_memory: Optional amount of memory for the model.
    - priority: Optional priority of the job.
    - csv_id_column: Optional CSV ID column name.
    - csv_strong_columns: Optional list of strong columns.
    - csv_weak_columns: Optional list of weak columns.
    - csv_reference_columns: Optional list of reference columns.
    - fhr: Optional FHR value.
    - embedding_dim: Optional embedding dimension.
    - output_dim: Optional output dimension.
    - max_in_memory_batches: Optional maximum number of in-memory batches.
    - extreme_num_hashes: Optional number of extreme hashes.
    - num_classes: Optional number of classes.
    - csv_query_column: Optional CSV query column name.
    - csv_id_delimiter: Optional CSV ID delimiter.
    - learning_rate: Optional learning rate.
    - batch_size: Optional batch size.
    - unsupervised_epochs: Optional number of unsupervised epochs.
    - supervised_epochs: Optional number of supervised epochs.
    - tokenizer: Optional tokenizer.
    - hidden_bias: Optional boolean indicating hidden bias.
    - retriever: Optional retriever to use.
    - unsupervised_train: Optional boolean indicating unsupervised training.
    - disable_finetunable_retriever: Optional boolean to disable finetunable retriever.
    - checkpoint_interval: Optional checkpoint interval.
    - fast_approximation: Optional boolean indicating fast approximation.
    - num_buckets_to_sample: Optional number of buckets to sample.
    - metrics: Optional list of metrics.
    - validation_metrics: Optional list of validation metrics.
    - on_disk: Optional boolean indicating on-disk storage.
    - docs_on_disk: Optional boolean indicating documents on-disk storage.

    Config:
    - extra: Forbid extra attributes.
    """

    # ----shard specific training params----
    num_models_per_shard: Optional[int] = Field(1, gt=0)
    num_shards: Optional[int] = Field(1, gt=0)
    allocation_cores: Optional[int] = None
    allocation_memory: Optional[int] = None

    # ----shard agnostic training params----
    model_cores: Optional[int] = None
    model_memory: Optional[int] = None
    priority: Optional[int] = None
    csv_id_column: Optional[str] = None
    csv_strong_columns: Optional[List[str]] = None
    csv_weak_columns: Optional[List[str]] = None
    csv_reference_columns: Optional[List[str]] = None
    fhr: Optional[int] = None
    embedding_dim: Optional[int] = None
    output_dim: Optional[int] = None
    max_in_memory_batches: Optional[int] = None
    extreme_num_hashes: Optional[int] = None
    num_classes: Optional[int] = None

    csv_query_column: Optional[str] = None
    csv_id_delimiter: Optional[str] = None

    learning_rate: Optional[float] = None
    batch_size: Optional[int] = None
    unsupervised_epochs: Optional[int] = None
    supervised_epochs: Optional[int] = None

    tokenizer: Optional[str] = None
    hidden_bias: Optional[bool] = None
    # This flag is for which retriever to use.
    retriever: Optional[str] = None
    unsupervised_train: Optional[bool] = None
    # This flag is to disable inverted index in supervised training.
    disable_finetunable_retriever: Optional[bool] = None
    checkpoint_interval: Optional[int] = None
    fast_approximation: Optional[bool] = None
    num_buckets_to_sample: Optional[int] = None
    metrics: Optional[List[str]] = None
    validation_metrics: Optional[List[str]] = None
    on_disk: Optional[bool] = None
    docs_on_disk: Optional[bool] = None

    class Config:
        extra = "forbid"


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
        template = Template(content)
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

    if json_payload_response.status_code != 200:
        raise ValueError(json_payload_response.text)

    json_payload = json_payload_response.json()

    # Submit the JSON job spec to Nomad
    response = requests.post(submit_url, headers=headers, json={"Job": json_payload})

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


GENERATE_JOB_ID = "llm-generation"


async def restart_generate_job():
    """
    Restart the LLM generation job.

    Returns:
    - Response: The response from the Nomad API.
    """
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
    if nomad_job_exists(GENERATE_JOB_ID, nomad_endpoint):
        delete_nomad_job(GENERATE_JOB_ID, nomad_endpoint)
    cwd = Path(os.getcwd())
    platform = get_platform()
    return submit_nomad_job(
        nomad_endpoint=nomad_endpoint,
        filepath=str(cwd / "backend" / "nomad_jobs" / "generation_job.hcl.j2"),
        platform=platform,
        port=None if platform == "docker" else get_empty_port(),
        tag=os.getenv("TAG"),
        registry=os.getenv("DOCKER_REGISTRY"),
        docker_username=os.getenv("DOCKER_USERNAME"),
        docker_password=os.getenv("DOCKER_PASSWORD"),
        image_name=os.getenv("GENERATION_IMAGE_NAME"),
        python_path=get_python_path(),
        generate_app_dir=str(get_root_absolute_path() / "llm_generation_job"),
    )


ON_PREM_GENERATE_JOB_ID = "on-prem-llm-generation"


async def restart_on_prem_generate_job():
    """
    Restart the LLM generation job.

    Returns:
    - Response: The response from the Nomad API.
    """
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
    if nomad_job_exists(ON_PREM_GENERATE_JOB_ID, nomad_endpoint):
        delete_nomad_job(ON_PREM_GENERATE_JOB_ID, nomad_endpoint)
    cwd = Path(os.getcwd())
    platform = get_platform()
    return submit_nomad_job(
        nomad_endpoint=nomad_endpoint,
        filepath=str(cwd / "backend" / "nomad_jobs" / "on_prem_generation_job.hcl.j2"),
        platform=platform,
        port=None if platform == "docker" else get_empty_port(),
        tag=os.getenv("TAG"),
        registry=os.getenv("DOCKER_REGISTRY"),
        docker_username=os.getenv("DOCKER_USERNAME"),
        docker_password=os.getenv("DOCKER_PASSWORD"),
        image_name=os.getenv("ON_PREM_GENERATION_IMAGE_NAME"),
        python_path=get_python_path(),
        generate_app_dir=str(get_root_absolute_path() / "on_prem_llm_generation_job"),
    )


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
