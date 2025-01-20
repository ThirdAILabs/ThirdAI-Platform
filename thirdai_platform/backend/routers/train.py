import io
import json
import logging
import os
import secrets
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
from auth.jwt import AuthenticatedUser, verify_access_token
from backend.auth_dependencies import verify_model_read_access
from backend.datagen import generate_data_for_train_job
from backend.utils import (
    copy_data_storage,
    delete_nomad_job,
    get_job_logs,
    get_model,
    get_model_from_identifier,
    get_model_status,
    get_platform,
    get_python_path,
    get_warnings_and_errors,
    nomad_job_exists,
    remove_unused_samples,
    retrieve_token_classification_samples_for_generation,
    submit_nomad_job,
    tags_in_storage,
    thirdai_platform_dir,
    update_json,
    validate_license_info,
    validate_name,
)
from data_generation_job.llms import verify_llm_access
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from platform_common.dependencies import is_on_low_disk
from platform_common.file_handler import download_local_files

pass
from platform_common.pii.defaults import NER_SOURCE_COLUMN, NER_TARGET_COLUMN
from platform_common.pydantic_models.feedback_logs import DeleteLog, InsertLog
from platform_common.pydantic_models.training import (
    DatagenOptions,
    FileInfo,
    FileLocation,
    JobOptions,
    LLMProvider,
    ModelType,
    NDBData,
    NDBOptions,
    TextClassificationOptions,
    TokenClassificationDatagenOptions,
    TokenClassificationOptions,
    TrainConfig,
    UDTData,
    UDTGeneratedData,
    UDTOptions,
    UDTSubType,
)
from platform_common.thirdai_storage import storage
from platform_common.utils import disk_usage, model_bazaar_path, response
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

train_router = APIRouter()


def get_base_model(base_model_identifier: str, user: schema.User, session: Session):
    try:
        base_model = get_model_from_identifier(base_model_identifier, session)
        if not base_model.get_user_permission(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to the specified base model.",
            )
        return base_model
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))


@train_router.post("/ndb", dependencies=[Depends(is_on_low_disk())])
def train_ndb(
    model_name: str,
    files: List[UploadFile],
    file_info: Optional[str] = Form(default="{}"),
    base_model_identifier: Optional[str] = None,
    model_options: str = Form(default="{}"),
    job_options: str = Form(default="{}"),
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    user: schema.User = authenticated_user.user
    try:
        model_options: NDBOptions = NDBOptions.model_validate_json(model_options)
        data = NDBData.model_validate_json(file_info)
        job_options = JobOptions.model_validate_json(job_options)
        logging.info(f"Extra options for training: {model_options}")
    except ValidationError as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Invalid options format: " + str(e),
        )

    license_info = validate_license_info()

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
    data_id = str(model_id)

    try:
        data = NDBData(
            unsupervised_files=download_local_files(
                files=files,
                file_infos=data.unsupervised_files,
                dest_dir=os.path.join(
                    model_bazaar_path(), "data", data_id, "unsupervised"
                ),
            ),
            supervised_files=download_local_files(
                files=files,
                file_infos=data.supervised_files,
                dest_dir=os.path.join(
                    model_bazaar_path(), "data", data_id, "supervised"
                ),
            ),
            test_files=download_local_files(
                files=files,
                file_infos=data.test_files,
                dest_dir=os.path.join(model_bazaar_path(), "data", data_id, "test"),
            ),
        )
    except Exception as error:
        return response(status_code=status.HTTP_400_BAD_REQUEST, message=str(error))

    # Base model checks
    base_model = None
    if base_model_identifier:
        base_model = get_base_model(base_model_identifier, user=user, session=session)

    config = TrainConfig(
        user_id=str(user.id),
        model_bazaar_dir=model_bazaar_path(),
        license_key=license_info["boltLicenseKey"],
        model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT", None),
        model_id=str(model_id),
        data_id=data_id,
        base_model_id=(None if not base_model_identifier else str(base_model.id)),
        model_options=model_options,
        data=data,
        job_options=job_options,
    )

    try:
        new_model = schema.Model(
            id=model_id,
            user_id=user.id,
            train_status=schema.Status.not_started,
            deploy_status=schema.Status.not_started,
            name=model_name,
            type=config.model_options.model_type.value,
            sub_type="v2",
            domain=user.domain,
            access_level=schema.Access.private,
            parent_id=base_model.id if base_model else None,
        )

        session.add(new_model)
        session.commit()
        session.refresh(new_model)
    except Exception as err:
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(err),
        )

    try:
        submit_nomad_job(
            str(Path(os.getcwd()) / "backend" / "nomad_jobs" / "train_job.hcl.j2"),
            nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
            platform=get_platform(),
            tag=os.getenv("TAG"),
            registry=os.getenv("DOCKER_REGISTRY"),
            docker_username=os.getenv("DOCKER_USERNAME"),
            docker_password=os.getenv("DOCKER_PASSWORD"),
            image_name=os.getenv("THIRDAI_PLATFORM_IMAGE_NAME"),
            thirdai_platform_dir=thirdai_platform_dir(),
            train_script="train_job.run",
            model_id=str(model_id),
            share_dir=os.getenv("SHARE_DIR", None),
            python_path=get_python_path(),
            aws_access_key=(os.getenv("AWS_ACCESS_KEY", "")),
            aws_access_secret=(os.getenv("AWS_ACCESS_SECRET", "")),
            aws_region_name=(os.getenv("AWS_REGION_NAME", "")),
            azure_account_name=(os.getenv("AZURE_ACCOUNT_NAME", "")),
            azure_account_key=(os.getenv("AZURE_ACCOUNT_KEY", "")),
            gcp_credentials_file=(os.getenv("GCP_CREDENTIALS_FILE", "")),
            openai_api_key=os.getenv("GENAI_KEY"),
            train_job_name=new_model.get_train_job_name(),
            config_path=config.save_train_config(),
            allocation_cores=job_options.allocation_cores,
            allocation_memory=job_options.allocation_memory,
            # TODO(Nicholas): Find a more graceful way to handle memory allocation for
            # larger training jobs
            allocation_memory_max=60_000,
        )

        new_model.train_status = schema.Status.starting
        session.commit()
    except Exception as err:
        new_model.train_status = schema.Status.failed
        session.commit()
        logging.error(str(err))
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
            "disk_usage": disk_usage(),
        },
    )


def list_insertions(deployment_dir: str) -> List[FileInfo]:
    insertions = []
    for logfile in os.listdir(os.path.join(deployment_dir, "insertions")):
        if logfile.endswith(".jsonl"):
            with open(os.path.join(deployment_dir, "insertions", logfile)) as f:
                for line in f.readlines():
                    insertions.extend(InsertLog.model_validate_json(line).documents)
    return insertions


def list_deletions(deployment_dir: str) -> List[str]:
    deletions = []
    for logfile in os.listdir(os.path.join(deployment_dir, "deletions")):
        if logfile.endswith(".jsonl"):
            with open(os.path.join(deployment_dir, "deletions", logfile)) as f:
                for line in f.readlines():
                    deletions.extend(DeleteLog.model_validate_json(line).doc_ids)
    return deletions


@train_router.post("/ndb-retrain", dependencies=[Depends(is_on_low_disk())])
def retrain_ndb(
    model_name: str,
    base_model_identifier: str,
    job_options: JobOptions = JobOptions(),
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    license_info = validate_license_info()

    user: schema.User = authenticated_user.user

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
    data_id = str(model_id)

    base_model = get_base_model(base_model_identifier, user=user, session=session)

    if base_model.type != ModelType.NDB:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"NDB retraining can only be performed on NDBv2 base models.",
        )

    deployment_dir = os.path.join(
        model_bazaar_path(),
        "models",
        str(base_model.id),
        "deployments",
        "data",
    )
    if not os.path.exists(deployment_dir) or len(os.listdir(deployment_dir)) == 0:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"No feedback found for base model {base_model_identifier}. Unable to perform retraining.",
        )

    unsupervised_files = list_insertions(deployment_dir)
    deletions = list_deletions(deployment_dir)

    feedback_dir = os.path.join(deployment_dir, "feedback")
    supervised_train_dir = os.path.join(
        model_bazaar_path(), "data", data_id, "supervised"
    )
    shutil.copytree(feedback_dir, supervised_train_dir)

    config = TrainConfig(
        user_id=str(user.id),
        model_bazaar_dir=model_bazaar_path(),
        license_key=license_info["boltLicenseKey"],
        model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT", None),
        model_id=str(model_id),
        data_id=data_id,
        base_model_id=(None if not base_model_identifier else str(base_model.id)),
        model_options=NDBOptions(),
        data=NDBData(
            unsupervised_files=unsupervised_files,
            supervised_files=[
                FileInfo(path=supervised_train_dir, location=FileLocation.nfs)
            ],
            deletions=deletions,
        ),
        job_options=job_options,
    )

    try:
        new_model = schema.Model(
            id=model_id,
            user_id=user.id,
            train_status=schema.Status.not_started,
            deploy_status=schema.Status.not_started,
            name=model_name,
            type=config.model_options.model_type.value,
            sub_type="v2",
            domain=user.domain,
            access_level=schema.Access.private,
            parent_id=base_model.id,
        )

        session.add(new_model)
        session.commit()
        session.refresh(new_model)
    except Exception as err:
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(err),
        )

    try:
        submit_nomad_job(
            str(Path(os.getcwd()) / "backend" / "nomad_jobs" / "train_job.hcl.j2"),
            nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
            platform=get_platform(),
            tag=os.getenv("TAG"),
            registry=os.getenv("DOCKER_REGISTRY"),
            docker_username=os.getenv("DOCKER_USERNAME"),
            docker_password=os.getenv("DOCKER_PASSWORD"),
            image_name=os.getenv("THIRDAI_PLATFORM_IMAGE_NAME"),
            thirdai_platform_dir=thirdai_platform_dir(),
            train_script="train_job.run",
            model_id=str(model_id),
            share_dir=os.getenv("SHARE_DIR", None),
            python_path=get_python_path(),
            aws_access_key=(os.getenv("AWS_ACCESS_KEY", "")),
            aws_access_secret=(os.getenv("AWS_ACCESS_SECRET", "")),
            aws_region_name=(os.getenv("AWS_REGION_NAME", "")),
            azure_account_name=(os.getenv("AZURE_ACCOUNT_NAME", "")),
            azure_account_key=(os.getenv("AZURE_ACCOUNT_KEY", "")),
            gcp_credentials_file=(os.getenv("GCP_CREDENTIALS_FILE", "")),
            train_job_name=new_model.get_train_job_name(),
            config_path=config.save_train_config(),
            allocation_cores=job_options.allocation_cores,
            allocation_memory=job_options.allocation_memory,
            allocation_memory_max=2 * job_options.allocation_memory,
        )

        new_model.train_status = schema.Status.starting
        session.commit()
    except Exception as err:
        new_model.train_status = schema.Status.failed
        session.commit()
        logging.error(str(err))
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
            "disk_usage": disk_usage(),
        },
    )


@train_router.post(
    "/nlp-datagen", dependencies=[Depends(is_on_low_disk(threshold=0.75))]
)
def nlp_datagen(
    model_name: str,
    base_model_identifier: Optional[str] = None,
    datagen_options: str = Form(default="{}"),
    datagen_job_options: str = Form(default="{}"),
    train_job_options: str = Form(default="{}"),
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    user: schema.User = authenticated_user.user
    try:
        datagen_options = DatagenOptions.model_validate_json(datagen_options)
        datagen_job_options = JobOptions.model_validate_json(datagen_job_options)
        train_job_options = JobOptions.model_validate_json(train_job_options)
        logging.info(f"Datagen options: {datagen_options}")
    except ValidationError as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Invalid options format: " + str(e),
        )

    license_info = validate_license_info()

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
    data_id = str(model_id)
    secret_token = secrets.token_hex(32)

    # Base model checks
    base_model = None
    if base_model_identifier:
        base_model = get_base_model(base_model_identifier, user=user, session=session)

    try:
        data = UDTGeneratedData(secret_token=secret_token)
    except Exception as error:
        return response(status_code=status.HTTP_400_BAD_REQUEST, message=str(error))

    if datagen_options.datagen_options.sub_type == UDTSubType.text:
        placeholder_udt_options = TextClassificationOptions(
            text_column="", label_column="", n_target_classes=0
        )
    else:
        placeholder_udt_options = TokenClassificationOptions(
            target_labels=[], source_column="", target_column=""
        )

    config = TrainConfig(
        user_id=str(user.id),
        model_bazaar_dir=model_bazaar_path(),
        license_key=license_info["boltLicenseKey"],
        model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT", None),
        model_id=str(model_id),
        data_id=data_id,
        base_model_id=(None if not base_model_identifier else str(base_model.id)),
        model_options=UDTOptions(udt_options=placeholder_udt_options),
        datagen_options=datagen_options,
        data=data,
        job_options=train_job_options,
    )

    config_path = os.path.join(
        config.model_bazaar_dir, "models", str(model_id), "train_config.json"
    )
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as file:
        file.write(config.model_dump_json(indent=4))

    try:
        new_model: schema.Model = schema.Model(
            id=model_id,
            user_id=user.id,
            train_status=schema.Status.not_started,
            deploy_status=schema.Status.not_started,
            name=model_name,
            type=ModelType.UDT,
            sub_type=datagen_options.datagen_options.sub_type,
            domain=user.email.split("@")[1],
            access_level=schema.Access.private,
            parent_id=base_model.id if base_model else None,
        )

        session.add(new_model)
        session.commit()
        session.refresh(new_model)

        attribute = schema.ModelAttribute(
            model_id=model_id,
            key="datagen",
            value="true",
        )
        session.add(attribute)
        session.commit()
    except Exception as err:
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(err),
        )

    try:
        # TODO: Ideally train job options are saved in the database instead of passed around to the datagen service
        generate_data_for_train_job(
            data_id=data_id,
            secret_token=secret_token,
            license_key=license_info["boltLicenseKey"],
            options=datagen_options,
            job_options=datagen_job_options,
        )

    except Exception as err:
        new_model.train_status = schema.Status.failed
        session.commit()
        logging.error(str(err))
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
            "disk_usage": disk_usage(),
        },
    )


@train_router.post("/datagen-callback", dependencies=[Depends(is_on_low_disk())])
def datagen_callback(
    data_id: str,
    secret_token: str,
    files: List[UploadFile] = [],
    file_info: Optional[str] = Form(default="{}"),
    model_options: str = Form(default="{}"),
    session: Session = Depends(get_session),
):
    try:
        model_options = UDTOptions.model_validate_json(model_options)
        data = UDTData.model_validate_json(file_info)
        logging.info(f"Extra options for training: {model_options}")
    except ValidationError as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Invalid options format: " + str(e),
        )

    license_info = validate_license_info()

    # We know this mapping is true because we set this in the nlp-datagen endpoint.
    model_id = data_id

    config_path = os.path.join(
        model_bazaar_path(), "models", str(model_id), "train_config.json"
    )
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "r") as file:
        config = TrainConfig.model_validate_json(file.read())

    if secret_token != config.data.secret_token:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Invalid datagen secret key.",
        )

    try:
        data = UDTData(
            supervised_files=download_local_files(
                files=files,
                file_infos=data.supervised_files,
                dest_dir=os.path.join(
                    model_bazaar_path(), "data", data_id, "supervised"
                ),
            ),
            test_files=download_local_files(
                files=files,
                file_infos=data.test_files,
                dest_dir=os.path.join(model_bazaar_path(), "data", data_id, "test"),
            ),
        )
    except Exception as error:
        return response(status_code=status.HTTP_400_BAD_REQUEST, message=str(error))

    # Update the config's model_options and data
    config.model_options = model_options
    config.data = data
    with open(config_path, "w") as file:
        file.write(config.model_dump_json(indent=4))

    model: schema.Model = session.query(schema.Model).get(model_id)

    try:
        if nomad_job_exists(model.get_train_job_name(), os.getenv("NOMAD_ENDPOINT")):
            delete_nomad_job(model.get_train_job_name(), os.getenv("NOMAD_ENDPOINT"))

        submit_nomad_job(
            str(Path(os.getcwd()) / "backend" / "nomad_jobs" / "train_job.hcl.j2"),
            nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
            platform=get_platform(),
            tag=os.getenv("TAG"),
            registry=os.getenv("DOCKER_REGISTRY"),
            docker_username=os.getenv("DOCKER_USERNAME"),
            docker_password=os.getenv("DOCKER_PASSWORD"),
            image_name=os.getenv("THIRDAI_PLATFORM_IMAGE_NAME"),
            thirdai_platform_dir=thirdai_platform_dir(),
            train_script="train_job.run",
            model_id=str(model_id),
            share_dir=os.getenv("SHARE_DIR", None),
            python_path=get_python_path(),
            aws_access_key=(os.getenv("AWS_ACCESS_KEY", "")),
            aws_access_secret=(os.getenv("AWS_ACCESS_SECRET", "")),
            aws_region_name=(os.getenv("AWS_REGION_NAME", "")),
            azure_account_name=(os.getenv("AZURE_ACCOUNT_NAME", "")),
            azure_account_key=(os.getenv("AZURE_ACCOUNT_KEY", "")),
            gcp_credentials_file=(os.getenv("GCP_CREDENTIALS_FILE", "")),
            train_job_name=model.get_train_job_name(),
            config_path=config_path,
            allocation_cores=config.job_options.allocation_cores,
            allocation_memory=config.job_options.allocation_memory,
            allocation_memory_max=config.job_options.allocation_memory,
        )

        model.train_status = schema.Status.starting
        session.commit()
    except Exception as err:
        # failed retraining job -> model is still valid
        # failed non-retraining job -> model is not valid
        if config.is_retraining:
            model.train_status = schema.Status.complete
        else:
            model.train_status = schema.Status.failed
        session.commit()

        logging.error(str(err))
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(err),
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully submitted the job",
        data={
            "model_id": str(model_id),
            "user_id": str(model.user_id),
        },
    )


@train_router.post("/retrain-udt", dependencies=[Depends(is_on_low_disk())])
def retrain_udt(
    model_name: str,
    llm_provider: LLMProvider,
    base_model_identifier: Optional[str] = None,
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    if base_model_identifier is not None:
        create_new_model with name model_name
    else:
        update existing model with name model_name
    """
    user: schema.User = authenticated_user.user
    license_info = validate_license_info()

    try:
        validate_name(model_name)
    except:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"{model_name} is not a valid model name.",
        )

    if base_model_identifier:
        base_model = get_base_model(base_model_identifier, user=user, session=session)
        if base_model is None:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Base model with id {base_model_identifier} does not exist.",
            )

        # create a new model
        model_id = uuid.uuid4()
        model: schema.Model = schema.Model(
            id=model_id,
            user_id=user.id,
            train_status=schema.Status.not_started,
            deploy_status=schema.Status.not_started,
            name=model_name,
            type=base_model.type,
            sub_type=base_model.sub_type,
            domain=user.email.split("@")[1],
            access_level=base_model.access_level,
            parent_id=base_model.id,
        )
        session.add(model)
        session.commit()
        session.refresh(model)

        attribute = schema.ModelAttribute(
            model_id=model_id,
            key="datagen",
            value="false",
        )
        session.add(attribute)
        session.commit()

    else:
        model = get_model(session, username=user.username, model_name=model_name)
        if model is None:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Model with name {model_name} does not exist for user {user.username}",
            )

    if model.type != ModelType.UDT and model.sub_type != UDTSubType.token:
        return response(
            status_cod=status.HTTP_400_BAD_REQUEST,
            message=f"Cannot retrain model of the type : {model.type}, subtype : {model.sub_type}. Only UDT Token Classification supported.",
        )

    if base_model_identifier:
        # if starting from a base model, copy the storage to the storage_dir of the new model
        # remove unused samples and rollback metadata to be in a consistent state
        copy_data_storage(base_model, model)
        remove_unused_samples(base_model)

    storage_dir = Path(model_bazaar_path()) / "data" / str(model.id)
    data_storage = storage.DataStorage(
        connector=storage.SQLiteConnector(db_path=storage_dir / "data_storage.db")
    )

    tags = tags_in_storage(data_storage)
    token_classification_samples = retrieve_token_classification_samples_for_generation(
        data_storage
    )

    token_classification_options = TokenClassificationDatagenOptions(
        sub_type=UDTSubType.token,
        tags=tags,
        num_sentences_to_generate=1_000,
        num_samples_per_tag=100,
        samples=token_classification_samples,
    )

    placeholder_udt_options = TokenClassificationOptions(
        target_labels=[], source_column="", target_column=""
    )

    secret_token = secrets.token_hex(32)
    try:
        data = UDTGeneratedData(secret_token=secret_token)
    except Exception as error:
        return response(status_code=status.HTTP_400_BAD_REQUEST, message=str(error))

    datagen_options = DatagenOptions(
        task_prompt="token_classification",
        llm_provider=llm_provider,
        datagen_options=token_classification_options,
    )

    config = TrainConfig(
        user_id=str(user.id),
        model_bazaar_dir=model_bazaar_path(),
        license_key=license_info["boltLicenseKey"],
        model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT", None),
        model_id=str(model.id),
        data_id=str(model.id),
        base_model_id=(None if not base_model_identifier else str(base_model.id)),
        model_options=UDTOptions(udt_options=placeholder_udt_options),
        datagen_options=datagen_options,
        data=data,
        job_options=JobOptions(),
        is_retraining=True if not base_model_identifier else False,
    )

    try:
        if verify_llm_access(llm_provider, api_key=os.getenv("GENAI_KEY")):
            logging.info("LLM access verified, generating data for training")

            config_path = config.save_train_config()

            generate_data_for_train_job(
                data_id=str(model.id),
                secret_token=secret_token,
                license_key=license_info["boltLicenseKey"],
                options=datagen_options,
                job_options=JobOptions(),
            )
        else:
            logging.info("No LLM access, training only on user provided samples")

            if nomad_job_exists(
                model.get_train_job_name(), os.getenv("NOMAD_ENDPOINT")
            ):
                delete_nomad_job(
                    model.get_train_job_name(), os.getenv("NOMAD_ENDPOINT")
                )

            config.model_options.udt_options = TokenClassificationOptions(
                target_labels=[tag.name for tag in tags],
                source_column=NER_SOURCE_COLUMN,
                target_column=NER_TARGET_COLUMN,
            )

            # Without any LLM access, the model should train only on the user provided samples present in the storage. Or balancing samples gathered from the training data. No file passed because user provided samples are already present in the storage.
            config.data = UDTData(supervised_files=[])

            config_path = config.save_train_config()

            logging.info("Triggered nomad job for training.")

            submit_nomad_job(
                str(Path(os.getcwd()) / "backend" / "nomad_jobs" / "train_job.hcl.j2"),
                nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
                platform=get_platform(),
                tag=os.getenv("TAG"),
                registry=os.getenv("DOCKER_REGISTRY"),
                docker_username=os.getenv("DOCKER_USERNAME"),
                docker_password=os.getenv("DOCKER_PASSWORD"),
                image_name=os.getenv("THIRDAI_PLATFORM_IMAGE_NAME"),
                thirdai_platform_dir=thirdai_platform_dir(),
                train_script="train_job.run",
                model_id=str(model.id),
                share_dir=os.getenv("SHARE_DIR", None),
                python_path=get_python_path(),
                aws_access_key=(os.getenv("AWS_ACCESS_KEY", "")),
                aws_access_secret=(os.getenv("AWS_ACCESS_SECRET", "")),
                aws_region_name=(os.getenv("AWS_REGION_NAME", "")),
                azure_account_name=(os.getenv("AZURE_ACCOUNT_NAME", "")),
                azure_account_key=(os.getenv("AZURE_ACCOUNT_KEY", "")),
                gcp_credentials_file=(os.getenv("GCP_CREDENTIALS_FILE", "")),
                train_job_name=model.get_train_job_name(),
                config_path=config_path,
                allocation_cores=config.job_options.allocation_cores,
                allocation_memory=config.job_options.allocation_memory,
                allocation_memory_max=config.job_options.allocation_memory,
            )

            model.train_status = schema.Status.starting
            session.commit()

    except Exception as err:
        model.train_status = schema.Status.failed
        session.commit()
        logging.error(str(err))
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(err),
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully submitted the job",
        data={
            "model_id": str(model.id),
            "user_id": str(user.id),
            "disk_usage": disk_usage(),
        },
    )


@train_router.post("/udt", dependencies=[Depends(is_on_low_disk())])
def train_udt(
    model_name: str,
    files: List[UploadFile] = [],
    file_info: Optional[str] = Form(default="{}"),
    base_model_identifier: Optional[str] = None,
    model_options: str = Form(default="{}"),
    job_options: str = Form(default="{}"),
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    user: schema.User = authenticated_user.user
    try:
        model_options = UDTOptions.model_validate_json(model_options)
        data = UDTData.model_validate_json(file_info)
        job_options = JobOptions.model_validate_json(job_options)
        logging.info(f"Extra options for training: {model_options}")
    except ValidationError as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Invalid options format: " + str(e),
        )

    license_info = validate_license_info()

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
    data_id = str(model_id)

    try:
        data = UDTData(
            supervised_files=download_local_files(
                files=files,
                file_infos=data.supervised_files,
                dest_dir=os.path.join(
                    model_bazaar_path(), "data", data_id, "supervised"
                ),
            ),
            test_files=download_local_files(
                files=files,
                file_infos=data.test_files,
                dest_dir=os.path.join(model_bazaar_path(), "data", data_id, "test"),
            ),
        )
    except Exception as error:
        return response(status_code=status.HTTP_400_BAD_REQUEST, message=str(error))

    # Base model checks
    base_model = None
    if base_model_identifier:
        base_model = get_base_model(base_model_identifier, user=user, session=session)

    config = TrainConfig(
        user_id=str(user.id),
        model_bazaar_dir=model_bazaar_path(),
        license_key=license_info["boltLicenseKey"],
        model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT", None),
        model_id=str(model_id),
        data_id=data_id,
        base_model_id=(None if not base_model_identifier else str(base_model.id)),
        model_options=model_options,
        data=data,
        job_options=job_options,
    )

    config_path = os.path.join(
        config.model_bazaar_dir, "models", str(model_id), "train_config.json"
    )
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as file:
        file.write(config.model_dump_json(indent=4))

    model_type = config.model_options.model_type.value
    model_sub_type = config.model_options.udt_options.udt_sub_type.value
    try:
        new_model: schema.Model = schema.Model(
            id=model_id,
            user_id=user.id,
            train_status=schema.Status.not_started,
            deploy_status=schema.Status.not_started,
            name=model_name,
            type=model_type,
            sub_type=model_sub_type,
            domain=user.email.split("@")[1],
            access_level=schema.Access.private,
            parent_id=base_model.id if base_model else None,
        )

        session.add(new_model)
        session.commit()
        session.refresh(new_model)

        attribute = schema.ModelAttribute(
            model_id=model_id,
            key="datagen",
            value="false",
        )
        session.add(attribute)
        session.commit()

    except Exception as err:
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(err),
        )

    if base_model:
        try:
            copy_data_storage(base_model, new_model)
            remove_unused_samples(base_model)
        except Exception as err:
            new_model.train_status = schema.Status.failed
            msg = "Unable to start training job. Encountered error loading data from specified base model."
            logging.error(f"error copying storage from ner base model: {err}")
            session.add(
                schema.JobError(
                    model_id=new_model.id,
                    job_type="train",
                    status=schema.Status.failed,
                    message=msg,
                )
            )
            session.commit()

            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=msg
            )

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
            image_name=os.getenv("THIRDAI_PLATFORM_IMAGE_NAME"),
            thirdai_platform_dir=thirdai_platform_dir(),
            train_script="train_job.run",
            model_id=str(model_id),
            share_dir=os.getenv("SHARE_DIR", None),
            python_path=get_python_path(),
            aws_access_key=(os.getenv("AWS_ACCESS_KEY", "")),
            aws_access_secret=(os.getenv("AWS_ACCESS_SECRET", "")),
            aws_region_name=(os.getenv("AWS_REGION_NAME", "")),
            azure_account_name=(os.getenv("AZURE_ACCOUNT_NAME", "")),
            azure_account_key=(os.getenv("AZURE_ACCOUNT_KEY", "")),
            gcp_credentials_file=(os.getenv("GCP_CREDENTIALS_FILE", "")),
            train_job_name=new_model.get_train_job_name(),
            config_path=config_path,
            allocation_cores=job_options.allocation_cores,
            allocation_memory=job_options.allocation_memory,
            allocation_memory_max=job_options.allocation_memory,
        )

        new_model.train_status = schema.Status.starting
        session.commit()
    except Exception as err:
        new_model.train_status = schema.Status.failed
        session.add(
            schema.JobError(
                model_id=new_model.id,
                job_type="train",
                status=schema.Status.failed,
                message=f"Failed to start the training job on nomad. Received error: {err}",
            )
        )
        session.commit()
        logging.error(str(err))
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
            "disk_usage": disk_usage(),
        },
    )


import aiofiles
import aiofiles.tempfile


async def validate_text_classification_csv_format(
    file: UploadFile,
) -> Tuple[bool, str, Set[str], None]:  # Changed return type annotation
    """
    Validates the CSV file format for text classification asynchronously using aiofiles.
    Returns (is_valid, error_message, extracted_labels).
    """
    # Check file extension
    if not file.filename.lower().endswith(".csv"):
        return False, "File must have .csv extension", None

    # Check MIME type
    if file.content_type not in ["text/csv", "application/csv"]:
        return False, "File must be a CSV", None

    try:
        # Create a temporary file using aiofiles
        async with aiofiles.tempfile.NamedTemporaryFile("wb+") as temp_file:
            # Read and write the uploaded file in chunks
            while chunk := await file.read(8192):  # 8KB chunks
                await temp_file.write(chunk)

            # Reset the temporary file pointer
            await temp_file.seek(0)

            # Read the temporary file content
            async with aiofiles.open(temp_file.name, mode="rb") as af:
                content = await af.read()

        # Process the CSV data
        df = pd.read_csv(io.BytesIO(content))

        if set(df.columns) != {"text", "label"}:
            return (
                False,
                "CSV must contain exactly two columns named 'text' and 'label'",
                None,
            )

        if df.empty:
            return False, "CSV file is empty", None

        if df["text"].isnull().any() or df["label"].isnull().any():
            return False, "CSV contains empty cells", None

        unique_labels = set(df["label"].unique())
        label_counts = df["label"].value_counts()
        insufficient_labels = {
            label for label, count in label_counts.items() if count < 10
        }

        if len(unique_labels) < 2:
            return False, "At least two different labels are required", unique_labels

        if insufficient_labels:
            return (
                False,
                f"Labels {', '.join(insufficient_labels)} have fewer than 10 examples",
                unique_labels,
            )

        return True, "", unique_labels

    except UnicodeDecodeError:
        return False, "File is not a valid CSV file (encoding error)", None
    except pd.errors.EmptyDataError:
        return False, "CSV file is empty", None
    except pd.errors.ParserError:
        return False, "File is not a valid CSV file (parsing error)", None
    except Exception as e:
        return False, f"Error validating CSV: {str(e)}", None


@train_router.post("/validate-text-classification-csv")
async def validate_text_classification_csv(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    try:
        is_valid, error_message, unique_labels = (
            await validate_text_classification_csv_format(file)
        )

        if not is_valid:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=error_message,
                data={"labels": list(unique_labels) if unique_labels else []},
            )

        return response(
            status_code=status.HTTP_200_OK,
            message="CSV file is valid",
            data={"labels": list(unique_labels)},
        )
    except Exception as e:
        return response(status_code=status.HTTP_400_BAD_REQUEST, message=str(e))


def validate_token_classification_csv_format(
    file: UploadFile,
) -> tuple[bool, str, Set[str], None]:
    """
    Validates the CSV file format for token classification.
    Returns (is_valid, error_message, extracted_labels).
    Validation rules:
    1. Must be valid CSV with exactly 'source' and 'target' columns
    2. Number of tokens must match between source and target
    3. Must have at least one non-'O' token type
    4. No empty cells allowed
    """
    # Check file extension
    if not file.filename.lower().endswith(".csv"):
        return False, "File must have .csv extension", None

    # Check MIME type
    if file.content_type not in ["text/csv", "application/csv"]:
        return False, "File must be a CSV", None

    try:
        content = file.file.read()
        file.file.seek(0)  # Reset file pointer for later use
        # Parse CSV
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
        # Check for required columns
        if set(df.columns) != {"source", "target"}:
            return (
                False,
                "CSV must contain exactly two columns named 'source' and 'target'",
                None,
            )
        # Check for empty dataframe
        if df.empty:
            return False, "CSV file is empty", None
        # Check for null values
        if df["source"].isnull().any() or df["target"].isnull().any():
            return False, "CSV contains empty cells", None
        # Validate token alignment
        for idx, row in df.iterrows():
            source_tokens = row["source"].split()
            target_tokens = row["target"].split()
            if len(source_tokens) != len(target_tokens):
                return (
                    False,
                    f"Row {idx + 1}: Number of tokens in source ({len(source_tokens)}) doesn't match target ({len(target_tokens)})",
                    None,
                )
        # Extract and validate token types
        token_types = set()
        for row in df["target"]:
            tokens = row.split()
            # Add all non-'O' tokens to our set
            token_types.update(token for token in tokens if token != "O")
        if not token_types:
            return (
                False,
                (
                    "No valid token types found in the target column. "
                    "The CSV must contain at least one token type other than 'O'. "
                    "The 'O' token is used to indicate non-entity tokens and cannot be the only token type."
                ),
                None,
            )
        # Log found token types for debugging
        logging.info(f"Found token types: {token_types}")
        return True, "", token_types
    except UnicodeDecodeError:
        return False, "File is not a valid CSV file (encoding error)", None
    except pd.errors.EmptyDataError:
        return False, "CSV file is empty", None
    except pd.errors.ParserError:
        return False, "File is not a valid CSV file (parsing error)", None
    except Exception as e:
        return False, f"Error validating CSV: {str(e)}", None


@train_router.post("/validate-token-classifier-csv")
def validate_token_classifier_csv(
    file: UploadFile = File(...),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Validate a CSV file for token classification training.
    Returns the detected labels if valid.
    """
    try:
        # Basic file type check
        if not file.filename.endswith(".csv"):
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="File must be a CSV",
                data={"valid": False, "details": "File must have .csv extension"},
            )
        # Validate CSV format and get labels
        is_valid, error_message, token_types = validate_token_classification_csv_format(
            file
        )
        if not is_valid:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=error_message,
                data={"valid": False, "details": error_message},
            )
        return response(
            status_code=status.HTTP_200_OK,
            message="CSV file is valid",
            data={
                "valid": True,
                "labels": list(token_types),
                "tokenTypeCount": len(token_types),
                "details": f"Found {len(token_types)} valid token types: {', '.join(sorted(token_types))}",
            },
        )
    except Exception as err:
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Error validating CSV: {str(err)}",
            data={"valid": False, "details": str(err)},
        )


class FolderValidationResponse(BaseModel):
    valid: bool
    message: str
    categories: List[str] = []
    file_counts: dict = {}


@train_router.post("/validate-document-classification-folder")
async def validate_document_classification_folder(
    files: List[UploadFile] = File(...),
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Validates a folder structure for document classification training.

    Expected folder structure when user selects a root folder (e.g., customer_feedback):
    customer_feedback/
    ├── positive/
    │   ├── comment_1.pdf
    │   ├── feedback_2.txt
    │   └── ...
    ├── neutral/
    │   ├── comment_3.docx
    │   ├── feedback_4.pdf
    │   └── ...
    ├── negative/
    │   ├── comment_5.pdf
    │   ├── feedback_6.txt
    │   └── ...

    Requirements:
    1. Only .txt, .doc, .docx, and .pdf files are allowed
    2. Must have at least 2 category folders (e.g., positive, neutral, negative)
    3. Each category must contain at least 10 documents
    4. Files must be organized in exactly 3 levels (root/category/files)
    5. No nested subcategories are allowed beyond the category level
    """
    try:
        valid_extensions = {".txt", ".doc", ".docx", ".pdf"}

        # Validate file types first
        invalid_files = []
        for file in files:
            ext = Path(file.filename).suffix.lower()
            if ext not in valid_extensions:
                invalid_files.append(file.filename)

        if invalid_files:
            return FolderValidationResponse(
                valid=False,
                message=f"Invalid file types found: {', '.join(invalid_files)}. Only .txt, .doc, .docx, and .pdf files are supported.",
                categories=[],
                file_counts={},
            )

        # Process files and validate folder structure
        categories = set()
        category_files = {}
        invalid_structure = []

        for file in files:
            parts = Path(file.filename).parts

            # Validate folder structure depth
            if len(parts) != 3:  # Exactly 3 levels: root/category/file.ext
                invalid_structure.append(file.filename)
                continue

            category = parts[1]
            categories.add(category)
            if category not in category_files:
                category_files[category] = []
            category_files[category].append(file.filename)

        # Check for invalid folder structure
        if invalid_structure:
            return FolderValidationResponse(
                valid=False,
                message=f"Invalid folder structure detected. Files must be inside category folders within the selected root folder. Invalid files: {', '.join(invalid_structure)}",
                categories=list(categories),
                file_counts=category_files,
            )

        if len(categories) < 2:
            return FolderValidationResponse(
                valid=False,
                message="At least two different categories (folders) are required",
                categories=list(categories),
                file_counts=category_files,
            )

        # Check minimum files per category
        insufficient_categories = []
        for category, files_list in category_files.items():
            if len(files_list) < 10:
                insufficient_categories.append(f"{category} ({len(files_list)} files)")

        if insufficient_categories:
            return FolderValidationResponse(
                valid=False,
                message=f"The following categories have fewer than 10 documents: {', '.join(insufficient_categories)}",
                categories=list(categories),
                file_counts=category_files,
            )

        return FolderValidationResponse(
            valid=True,
            message="Folder structure is valid",
            categories=list(categories),
            file_counts=category_files,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@train_router.get("/train-report", dependencies=[Depends(verify_model_read_access)])
def train_report(model_identifier: str, session: Session = Depends(get_session)):
    try:
        model: schema.Model = get_model_from_identifier(model_identifier, session)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    if model.train_status != schema.Status.complete:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Cannot get train report for model {model_identifier} since training is not completed.",
        )

    report_dir = os.path.join(
        model_bazaar_path(), "models", str(model.id), "train_reports"
    )
    if not os.path.exists(report_dir) or len(os.listdir(report_dir)) == 0:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=(
                f"No training reports found for model {model_identifier}. Train reports "
                "are currently only availible for token classification use cases and if a test set "
                "or test_split is provided."
            ),
        )

    reports = os.listdir(report_dir)
    most_recent_report = max([int(os.path.splitext(report)[0]) for report in reports])

    with open(os.path.join(report_dir, f"{most_recent_report}.json")) as f:
        report = json.load(f)

    return response(
        status_code=status.HTTP_200_OK, message="Retrieved train report", data=report
    )


class TrainComplete(BaseModel):
    model_id: str
    metadata: Dict[str, str]

    class Config:
        protected_namespaces = ()


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
    new_status: schema.Status,
    message: Optional[str] = None,
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

    trained_model.train_status = new_status
    if new_status == schema.Status.failed and message:
        session.add(
            schema.JobMessage(
                model_id=trained_model.id,
                job_type="train",
                level=schema.Level.error,
                message=message,
            )
        )
    session.commit()

    return {"message": f"successfully updated with following {message}"}


@train_router.post("/warning")
def train_warning(model_id: str, message: str, session: Session = Depends(get_session)):
    trained_model: schema.Model = (
        session.query(schema.Model).filter(schema.Model.id == model_id).first()
    )

    if not trained_model:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"No model with id {model_id}.",
        )

    session.add(
        schema.JobMessage(
            model_id=trained_model.id,
            job_type="train",
            level=schema.Level.warning,
            message=message,
        )
    )
    session.commit()

    return {"message": "successfully logged the message"}


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

    train_status, reasons = get_model_status(model, train_status=True)
    warnings, errors = get_warnings_and_errors(session, model, job_type="train")
    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the train status.",
        data={
            "model_identifier": model_identifier,
            "train_status": train_status,
            "messages": reasons,
            "warnings": warnings,
            "errors": errors,
        },
    )


@train_router.get("/logs", dependencies=[Depends(verify_model_read_access)])
def train_logs(
    model_identifier: str,
    session: Session = Depends(get_session),
):
    try:
        model: schema.Model = get_model_from_identifier(model_identifier, session)
    except Exception as error:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(error),
        )

    logs = get_job_logs(
        nomad_endpoint=os.getenv("NOMAD_ENDPOINT"), model=model, job_type="train"
    )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the train logs.",
        data=logs,
    )
