import json
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from auth.jwt import AuthenticatedUser, verify_access_token
from backend.auth_dependencies import verify_model_read_access
from backend.file_handler import (
    FileLocation,
    FileType,
    NDBFileDetails,
    NDBFileDetailsList,
    UDTFileDetails,
    UDTFileDetailsList,
    get_files,
)
from backend.utils import (
    NDBExtraOptions,
    UDTExtraOptions,
    get_model,
    get_model_from_identifier,
    get_nomad_job,
    get_platform,
    get_python_path,
    get_root_absolute_path,
    logger,
    response,
    submit_nomad_job,
    update_json,
    validate_name,
)
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, Form, UploadFile, status
from fastapi.encoders import jsonable_encoder
from licensing.verify.verify_license import valid_job_allocation, verify_license
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

train_router = APIRouter()


@train_router.post("/ndb")
def train_ndb(
    model_name: str,
    files: List[UploadFile],
    file_details_list: Optional[str] = Form(default=None),
    base_model_identifier: Optional[str] = None,
    extra_options_form: str = Form(default="{}"),
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Train a NeuralDB model.

    Parameters:
    - model_name: The name of the model.
    - files: List of files to be used for training.
    - file_details_list: Optional JSON string of file details.
        - Example:
        ```json
        {
            "file_details": [
                {
                    "mode": "unsupervised",
                    "location": "local",
                    "is_folder": false,
                    "source_id": null,
                    "metadata": {
                        "key1": "value1",
                        "key2": "value2"
                    }
                }
            ]
        }
        ```
        - Supported modes: "unsupervised", "supervised", "test"
        - Supported locations: "local", "nfs", "s3"
    - base_model_identifier: Optional identifier of the base model.
    - extra_options_form: Optional JSON string of extra options for training.
        - Example:
        ```json
        {
            "num_models_per_shard": 1,
            "num_shards": 1,
            "allocation_cores": 4,
            "allocation_memory": 8192,
            "model_cores": 4,
            "model_memory": 8192,
            "priority": 1,
            "csv_id_column": "id",
            "csv_strong_columns": ["column1", "column2"],
            "csv_weak_columns": ["column3"],
            "csv_reference_columns": ["reference_column"],
            "fhr": 100,
            "embedding_dim": 256,
            "output_dim": 128,
            "max_in_memory_batches": 10,
            "extreme_num_hashes": 10,
            "num_classes": 2,
            "csv_query_column": "query",
            "csv_id_delimiter": ",",
            "learning_rate": 0.01,
            "batch_size": 32,
            "unsupervised_epochs": 10,
            "supervised_epochs": 10,
            "tokenizer": "default",
            "hidden_bias": true,
            "retriever": "default",
            "unsupervised_train": true,
            "disable_finetunable_retriever": false,
            "checkpoint_interval": 100,
            "fast_approximation": false,
            "num_buckets_to_sample": 10,
            "metrics": ["accuracy", "f1"],
            "on_disk": false,
            "docs_on_disk": false
        }
        ```
    - session: The database session (dependency).
    - authenticated_user: The authenticated user (dependency).

    Returns:
    - A JSON response indicating the status of the training job submission.
    """
    user: schema.User = authenticated_user.user
    try:
        extra_options = NDBExtraOptions.parse_raw(extra_options_form).dict()
        extra_options = {k: v for k, v in extra_options.items() if v is not None}
        if extra_options:
            print(f"Extra options for training: {extra_options}")
    except ValidationError as e:
        return {"error": "Invalid extra options format", "details": str(e)}

    if file_details_list:
        try:
            files_info_list = NDBFileDetailsList.parse_raw(file_details_list)
            files_info = [
                NDBFileDetails(**detail.dict())
                for detail in files_info_list.file_details
            ]
        except ValidationError as e:
            return {"error": "Invalid file details list format", "details": str(e)}
    else:
        files_info = [
            NDBFileDetails(mode=FileType.unsupervised, location=FileLocation.local)
            for _ in files
        ]

    try:
        license_info = verify_license(
            os.getenv(
                "LICENSE_PATH", "/model_bazaar/license/ndb_enterprise_license.json"
            )
        )
        if not valid_job_allocation(license_info, os.getenv("NOMAD_ENDPOINT")):
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Resource limit reached, cannot allocate new jobs.",
            )
    except Exception as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"License is not valid. {str(e)}",
        )

    try:
        validate_name(model_name)
    except:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"{model_name} is not a valid model name.",
        )

    duplicate_model = get_model(session, username=user.username, model_name=model_name)
    if duplicate_model:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Model with name {model_name} already exists for user {user.username}.",
        )

    model_id = uuid.uuid4()
    data_id = model_id

    if len(files) != len(files_info):
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Given {len(files)} files but for {len(files_info)} files the info has given.",
        )

    filenames = get_files(files, data_id, files_info)

    if not isinstance(filenames, list):
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=filenames,
        )

    if len(filenames) == 0:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="No files provided.",
        )

    unique_filenames = set(filenames)
    if len(filenames) != len(unique_filenames):
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Duplicate filenames received, please ensure each filename is unique.",
        )

    # Base model checks
    base_model = None
    if base_model_identifier:
        try:
            base_model = get_model_from_identifier(base_model_identifier, session)
            if not base_model.get_user_permission(user):
                return response(
                    status_code=status.HTTP_403_FORBIDDEN,
                    message="You do not have access to the specified base model.",
                )
        except Exception as error:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=str(error),
            )

    sharded = (
        True
        if extra_options.get("num_models_per_shard") > 1
        or extra_options.get("num_shards") > 1
        else False
    )

    new_model = schema.Model(
        id=model_id,
        user_id=user.id,
        train_status=schema.Status.not_started,
        deploy_status=schema.Status.not_started,
        name=model_name,
        type="ndb",
        sub_type="single" if not sharded else "sharded",
        domain=user.domain,
        access_level=schema.Access.private,
        parent_id=base_model.id if base_model else None,
    )

    session.add(new_model)
    session.commit()
    session.refresh(new_model)

    work_dir = os.getcwd()

    try:
        submit_nomad_job(
            str(Path(work_dir) / "backend" / "nomad_jobs" / "train_job.hcl.j2"),
            nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
            platform=get_platform(),
            tag=os.getenv("TAG"),
            registry=os.getenv("DOCKER_REGISTRY"),
            docker_username=os.getenv("DOCKER_USERNAME"),
            docker_password=os.getenv("DOCKER_PASSWORD"),
            image_name=os.getenv("TRAIN_IMAGE_NAME"),
            train_script=str(get_root_absolute_path() / "train_job/run.py"),
            model_id=str(model_id),
            data_id=str(data_id),
            model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT", None),
            share_dir=os.getenv("SHARE_DIR", None),
            license_key=license_info["boltLicenseKey"],
            extra_options=extra_options,
            python_path=get_python_path(),
            aws_access_key=(os.getenv("AWS_ACCESS_KEY", "")),
            aws_access_secret=(os.getenv("AWS_ACCESS_SECRET", "")),
            base_model_id=("NONE" if not base_model_identifier else str(base_model.id)),
            type="ndb",
            sub_type="single" if not sharded else "shard_allocation",
        )

        new_model.train_status = schema.Status.starting
        session.commit()
    except Exception as err:
        # TODO: change the status of the new model entry to failed

        logger.info(str(err))
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(err),
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully submitted the job",
        data={
            "model_id": str(model_id),
            "user_id": str(user.id),
        },
    )


@train_router.post("/udt")
def train_udt(
    model_name: str,
    files: List[UploadFile],
    file_details_list: Optional[str] = Form(default=None),
    base_model_identifier: Optional[str] = None,
    extra_options_form: str = Form(default="{}"),
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Train a UDT model.

    Parameters:
    - model_name: The name of the model.
    - files: List of files to be used for training.
    - file_details_list: Optional JSON string of file details.
        - Example:
        ```json
        {
            "file_details": [
                {
                    "mode": "supervised",
                    "location": "local",
                    "is_folder": false,
                }
            ]
        }
        ```
        - Supported modes: "supervised", "test" (UDT files cannot be in "unsupervised" mode)
        - Supported locations: "local", "nfs", "s3"
    - base_model_identifier: Optional identifier of the base model.
    - extra_options_form: Optional JSON string of extra options for training.
        - Example:
        ```json
        {
            "allocation_cores": 4,
            "allocation_memory": 8192,
            "sub_type": "text",
            "target_labels": ["label1", "label2"],
            "source_column": "source",
            "target_column": "target",
            "default_tag": "O",
            "delimiter": ",",
            "text_column": "text",
            "label_column": "label",
            "n_target_classes": 2
        }
        ```
    - session: The database session (dependency).
    - authenticated_user: The authenticated user (dependency).

    Returns:
    - A JSON response indicating the status of the training job submission.
    """
    user: schema.User = authenticated_user.user
    try:
        extra_options = UDTExtraOptions.parse_raw(extra_options_form).dict()
        extra_options = {k: v for k, v in extra_options.items() if v is not None}
        if extra_options:
            print(f"Extra options for training: {extra_options}")
    except ValidationError as e:
        return {"error": "Invalid extra options format", "details": str(e)}

    if file_details_list:
        try:
            files_info_list = UDTFileDetailsList.parse_raw(file_details_list)
            files_info = [
                UDTFileDetails(**detail.dict())
                for detail in files_info_list.file_details
            ]
        except ValidationError as e:
            return {"error": "Invalid file details list format", "details": str(e)}
    else:
        files_info = [
            UDTFileDetails(mode=FileType.supervised, location=FileLocation.local)
            for _ in files
        ]

    try:
        license_info = verify_license(
            os.getenv(
                "LICENSE_PATH", "/model_bazaar/license/ndb_enterprise_license.json"
            )
        )
        if not valid_job_allocation(license_info, os.getenv("NOMAD_ENDPOINT")):
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Resource limit reached, cannot allocate new jobs.",
            )
    except Exception as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"License is not valid. {str(e)}",
        )

    try:
        validate_name(model_name)
    except:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"{model_name} is not a valid model name.",
        )

    duplicate_model = get_model(session, username=user.username, model_name=model_name)
    if duplicate_model:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Model with name {model_name} already exists for user {user.username}.",
        )

    model_id = uuid.uuid4()
    data_id = model_id

    if len(files) != len(files_info):
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Given {len(files)} files but for {len(files_info)} files the info has given.",
        )

    filenames = get_files(files, data_id, files_info)

    if not isinstance(filenames, list):
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=filenames,
        )

    if len(filenames) == 0:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="No files provided.",
        )

    unique_filenames = set(filenames)
    if len(filenames) != len(unique_filenames):
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Duplicate filenames received, please ensure each filename is unique.",
        )

    # Base model checks
    base_model = None
    if base_model_identifier:
        try:
            base_model = get_model_from_identifier(base_model_identifier, session)
            if not base_model.get_user_permission(user):
                return response(
                    status_code=status.HTTP_403_FORBIDDEN,
                    message="You do not have access to the specified base model.",
                )
        except Exception as error:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=str(error),
            )

    new_model: schema.Model = schema.Model(
        id=model_id,
        user_id=user.id,
        train_status=schema.Status.not_started,
        deploy_status=schema.Status.not_started,
        name=model_name,
        type="udt",
        sub_type=extra_options["sub_type"],
        domain=user.email.split("@")[1],
        access_level=schema.Access.private,
        parent_id=base_model.id if base_model else None,
    )

    session.add(new_model)
    session.commit()
    session.refresh(new_model)

    work_dir = os.getcwd()

    udt_subtype = extra_options["sub_type"]
    extra_options.pop("sub_type", None)

    try:
        submit_nomad_job(
            str(Path(work_dir) / "backend" / "nomad_jobs" / "train_job.hcl.j2"),
            nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
            platform=get_platform(),
            tag=os.getenv("TAG"),
            registry=os.getenv("DOCKER_REGISTRY"),
            docker_username=os.getenv("DOCKER_USERNAME"),
            docker_password=os.getenv("DOCKER_PASSWORD"),
            image_name=os.getenv("TRAIN_IMAGE_NAME"),
            train_script=str(get_root_absolute_path() / "train_job/run.py"),
            model_id=str(model_id),
            data_id=str(data_id),
            model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT", None),
            share_dir=os.getenv("SHARE_DIR", None),
            license_key=license_info["boltLicenseKey"],
            extra_options=extra_options,
            python_path=get_python_path(),
            aws_access_key=(os.getenv("AWS_ACCESS_KEY", "")),
            aws_access_secret=(os.getenv("AWS_ACCESS_SECRET", "")),
            base_model_id=("NONE" if not base_model_identifier else str(base_model.id)),
            type="udt",
            sub_type=udt_subtype,
        )

        new_model.train_status = schema.Status.starting
        session.commit()
    except Exception as err:
        # TODO: change the status of the new model entry to failed
        logger.info(str(err))
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(err),
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully submitted the job",
        data={
            "model_id": str(model_id),
            "user_id": str(user.id),
        },
    )


class TrainComplete(BaseModel):
    model_id: str
    metadata: Dict[str, str]


@train_router.post("/complete")
def train_complete(
    body: TrainComplete,
    session: Session = Depends(get_session),
):
    """
    Mark the training of a model as complete.

    Parameters:
    - body: The body of the request containing model_id and metadata.
        - Example:
        ```json
        {
            "model_id": "123e4567-e89b-12d3-a456-426614174000",
            "metadata": {
                "accuracy": "0.95",
                "f1_score": "0.92"
            }
        }
        ```
    - session: The database session (dependency).

    Returns:
    - A JSON response indicating the update status.
    """
    trained_model: schema.Model = (
        session.query(schema.Model).filter(schema.Model.id == body.model_id).first()
    )
    if not trained_model:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"No model with id {body.model_id}.",
        )

    trained_model.train_status = schema.Status.complete

    metadata: schema.MetaData = trained_model.meta_data
    if metadata:
        metadata.train = update_json(metadata.train, body.metadata)
    else:
        new_metadata = schema.MetaData(
            model_id=trained_model.id,
            train=json.dumps(body.metadata),
        )
        session.add(new_metadata)

    session.commit()

    return {"message": "Successfully updated"}


@train_router.post("/update-status")
def train_fail(
    model_id: str,
    status: schema.Status,
    message: str,
    session: Session = Depends(get_session),
):
    """
    Update the training status of a model.

    Parameters:
    - model_id: The ID of the model.
    - status: The new status for the model (e.g., "failed", "in_progress").
    - message: A message describing the update.
        - Example:
        ```json
        {
            "model_id": "123e4567-e89b-12d3-a456-426614174000",
            "status": "failed",
            "message": "Training failed due to insufficient data."
        }
        ```
    - session: The database session (dependency).

    Returns:
    - A JSON response indicating the update status.
    """
    trained_model: schema.Model = (
        session.query(schema.Model).filter(schema.Model.id == model_id).first()
    )

    if not trained_model:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"No model with id {model_id}.",
        )

    trained_model.train_status = status
    session.commit()

    return {"message": f"successfully updated with following {message}"}


@train_router.post("/create-shard")
def create_shard(
    shard_num: int,
    model_id: str,
    data_id: str,
    base_model_id: Optional[str] = None,
    extra_options_form: str = Form(default="{}"),
    session: Session = Depends(get_session),
):
    """
    Create a shard for training a NeuralDB model.

    Parameters:
    - shard_num: The shard number.
    - model_id: The ID of the model.
    - data_id: The ID of the data.
    - base_model_id: Optional ID of the base model.
    - extra_options_form: Optional JSON string of extra options for training.
        - Example:
        ```json
        {
            "num_models_per_shard": 1,
            "num_shards": 1,
            "allocation_cores": 4,
            "allocation_memory": 8192,
            "model_cores": 4,
            "model_memory": 8192,
            "priority": 1,
            "csv_id_column": "id",
            "csv_strong_columns": ["column1", "column2"],
            "csv_weak_columns": ["column3"],
            "csv_reference_columns": ["reference_column"],
            "fhr": 100,
            "embedding_dim": 256,
            "output_dim": 128,
            "max_in_memory_batches": 10,
            "extreme_num_hashes": 10,
            "num_classes": 2,
            "csv_query_column": "query",
            "csv_id_delimiter": ",",
            "learning_rate": 0.01,
            "batch_size": 32,
            "unsupervised_epochs": 10,
            "supervised_epochs": 10,
            "tokenizer": "default",
            "hidden_bias": true,
            "retriever": "default",
            "unsupervised_train": true,
            "disable_finetunable_retriever": false,
            "checkpoint_interval": 100,
            "fast_approximation": false,
            "num_buckets_to_sample": 10,
            "metrics": ["accuracy", "f1"],
            "on_disk": false,
            "docs_on_disk": false
        }
        ```
    - session: The database session (dependency).

    Returns:
    - A JSON response indicating the shard creation status.
    """
    try:
        extra_options = NDBExtraOptions.parse_raw(extra_options_form).dict()
        extra_options = {k: v for k, v in extra_options.items() if v is not None}
        if extra_options:
            print(f"Extra options for shard training: {extra_options}")
    except ValidationError as e:
        return {"error": "Invalid extra options format", "details": str(e)}

    try:
        license_info = verify_license(
            os.getenv(
                "LICENSE_PATH", "/model_bazaar/license/ndb_enterprise_license.json"
            )
        )
    except Exception as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"License is not valid. {str(e)}",
        )

    new_shard: schema.ModelShard = schema.ModelShard(
        model_id=model_id,
        shard_num=shard_num,
        train_status=schema.Status.not_started,
    )
    session.add(new_shard)
    session.commit()

    work_dir = os.getcwd()

    try:
        submit_nomad_job(
            str(Path(work_dir) / "backend" / "nomad_jobs" / "train_job.hcl.j2"),
            nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
            platform=get_platform(),
            tag=os.getenv("TAG"),
            registry=os.getenv("DOCKER_REGISTRY"),
            docker_username=os.getenv("DOCKER_USERNAME"),
            docker_password=os.getenv("DOCKER_PASSWORD"),
            image_name=os.getenv("TRAIN_IMAGE_NAME"),
            train_script=str(get_root_absolute_path() / "train_job/run.py"),
            model_id=str(model_id),
            data_id=str(data_id),
            model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT", None),
            share_dir=os.getenv("SHARE_DIR", None),
            license_key=license_info["boltLicenseKey"],
            extra_options=extra_options,
            python_path=get_python_path(),
            type="ndb",
            sub_type="shard_train",
            base_model_id="NONE" if not base_model_id else base_model_id,
            shard_num=shard_num,
        )

        new_shard.train_status = schema.Status.starting
        session.commit()
    except Exception as err:
        logger.info(str(err))
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(err),
        )

    return {"message": f"Successfully created shard"}


@train_router.post("/update-shard-train-status")
def update_shard_train_status(
    shard_num: int,
    model_id: str,
    status: schema.Status,
    message: str = "",
    session: Session = Depends(get_session),
):
    """
    Update the training status of a model shard.

    Parameters:
    - shard_num: The shard number.
    - model_id: The ID of the model.
    - status: The new status for the shard (e.g., "failed", "in_progress").
    - message: A message describing the update.
        - Example:
        ```json
        {
            "shard_num": 1,
            "model_id": "123e4567-e89b-12d3-a456-426614174000",
            "status": "in_progress",
            "message": "Shard training in progress."
        }
        ```
    - session: The database session (dependency).

    Returns:
    - A JSON response indicating the update status.
    """
    model_shard: schema.ModelShard = (
        session.query(schema.ModelShard)
        .filter(
            schema.ModelShard.model_id == model_id,
            schema.ModelShard.shard_num == shard_num,
        )
        .first()
    )

    if not model_shard:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"No model shard with id {model_id} and shard number {shard_num}.",
        )

    model_shard.train_status = status
    session.commit()

    return {"message": f"Successfully updated shard with message: {message}"}


@train_router.get("/status", dependencies=[Depends(verify_model_read_access)])
def train_status(
    model_identifier: str,
    session: Session = Depends(get_session),
):
    """
    Get the status of a NeuralDB.

    Parameters:
    - model_identifier: The identifier of the model to retrieve info about.
    - session: The database session (dependency).
    - authenticated_user: The authenticated user (dependency).

    Returns:
    - A JSON response with the model status.
    """
    try:
        model: schema.Model = get_model_from_identifier(model_identifier, session)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the train status.",
        data={
            "model_identifier": model_identifier,
            "train_status": model.train_status,
        },
    )


@train_router.get(
    "/model-shard-train-status", dependencies=[Depends(verify_model_read_access)]
)
def model_shard_train_status(
    model_id: str,
    session: Session = Depends(get_session),
):
    """
    Get the training status of all shards for a given model.

    Parameters:
    - model_id: The ID of the model.
    - session: The database session (dependency).

    Returns:
    - A JSON response with the training status of all shards.
    """
    try:
        model_shards: List[schema.ModelShard] = (
            session.query(schema.ModelShard)
            .filter(schema.ModelShard.model_id == model_id)
            .all()
        )
    except Exception as error:
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(error),
        )

    if not model_shards:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="No shards found for the given model id.",
        )

    results = [
        {
            "shard_num": result.shard_num,
            "status": result.train_status,
        }
        for result in model_shards
    ]

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the train status.",
        data=jsonable_encoder(results),
    )


@train_router.post("/sync-status")
def sync_model_bazaar(
    session: Session = Depends(get_session),
):
    models: list[schema.Model] = session.query(schema.Model).all()

    for model in models:
        if (
            model.train_status == schema.Status.starting
            or model.train_status == schema.Status.in_progress
        ):
            model_data = get_nomad_job(
                model.get_train_job_name(), os.getenv("NOMAD_ENDPOINT")
            )
            if not model_data or model_data["Status"] == "dead":
                model.train_status = schema.Status.failed

        if model.deploy_status == schema.Status.starting:
            deployment_data = get_nomad_job(
                model.get_deployment_name(), os.getenv("NOMAD_ENDPOINT")
            )
            if not deployment_data or deployment_data["Status"] == "dead":
                model.deploy_status = schema.Status.failed

    session.commit()

    return {"message": "successfully synced models"}
