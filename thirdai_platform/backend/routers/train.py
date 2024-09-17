import json
import os
import secrets
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from auth.jwt import AuthenticatedUser, verify_access_token
from backend.auth_dependencies import verify_model_read_access
from backend.config import (
    DatagenOptions,
    FileInfo,
    FileLocation,
    JobOptions,
    ModelType,
    NDBData,
    NDBOptions,
    NDBSubType,
    NDBv2Options,
    TextClassificationOptions,
    TokenClassificationOptions,
    TrainConfig,
    UDTData,
    UDTGeneratedData,
    UDTOptions,
    UDTSubType,
)
from backend.datagen import generate_data_for_train_job
from backend.file_handler import download_local_files, model_bazaar_path
from backend.utils import (
    get_model,
    get_model_from_identifier,
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
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from licensing.verify.verify_license import valid_job_allocation, verify_license
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

train_router = APIRouter()


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


@train_router.post("/ndb")
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
        model_options = NDBOptions.model_validate_json(model_options)
        data = NDBData.model_validate_json(file_info)
        job_options = JobOptions.model_validate_json(job_options)
        print(f"Extra options for training: {model_options}")
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
            sub_type=config.model_options.ndb_options.ndb_sub_type.value,
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
            image_name=os.getenv("TRAIN_IMAGE_NAME"),
            train_script=str(get_root_absolute_path() / "train_job/run.py"),
            model_id=str(model_id),
            share_dir=os.getenv("SHARE_DIR", None),
            python_path=get_python_path(),
            aws_access_key=(os.getenv("AWS_ACCESS_KEY", "")),
            aws_access_secret=(os.getenv("AWS_ACCESS_SECRET", "")),
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


class InsertLog(BaseModel):
    documents: List[FileInfo]


class DeleteLog(BaseModel):
    doc_ids: List[str]


def list_insertions(deployment_dir: str) -> List[FileInfo]:
    insertions = []
    for logfile in os.path.join(deployment_dir, "insertions"):
        if logfile.endswith(".jsonl"):
            with open(os.path.join(deployment_dir, "insertions", logfile)) as f:
                for line in f.readlines():
                    insertions.extend(InsertLog.model_validate_json(line).documents)
    return insertions


def list_deletions(deployment_dir: str) -> List[str]:
    deletions = []
    for logfile in os.path.join(deployment_dir, "deletions"):
        if logfile.endswith(".jsonl"):
            with open(os.path.join(deployment_dir, "deletions", logfile)) as f:
                for line in f.readlines():
                    deletions.extend(DeleteLog.model_validate_json(line).doc_ids)
    return deletions



@train_router.post("/ndb-retrain")
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

    if base_model.type != ModelType.NDB or base_model.sub_type != NDBSubType.v2:
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
        model_bazaar_dir=model_bazaar_path(),
        license_key=license_info["boltLicenseKey"],
        model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT", None),
        model_id=str(model_id),
        data_id=data_id,
        base_model_id=(None if not base_model_identifier else str(base_model.id)),
        model_options=NDBOptions(ndb_options=NDBv2Options()),
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
            sub_type=config.model_options.ndb_options.ndb_sub_type.value,
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
            image_name=os.getenv("TRAIN_IMAGE_NAME"),
            train_script=str(get_root_absolute_path() / "train_job/run.py"),
            model_id=str(model_id),
            share_dir=os.getenv("SHARE_DIR", None),
            python_path=get_python_path(),
            aws_access_key=(os.getenv("AWS_ACCESS_KEY", "")),
            aws_access_secret=(os.getenv("AWS_ACCESS_SECRET", "")),
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


@train_router.post("/nlp-datagen")
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
        print(f"Datagen options: {datagen_options}")
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


@train_router.post("/datagen-callback")
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
        print(f"Extra options for training: {model_options}")
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
        submit_nomad_job(
            str(Path(os.getcwd()) / "backend" / "nomad_jobs" / "train_job.hcl.j2"),
            nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
            platform=get_platform(),
            tag=os.getenv("TAG"),
            registry=os.getenv("DOCKER_REGISTRY"),
            docker_username=os.getenv("DOCKER_USERNAME"),
            docker_password=os.getenv("DOCKER_PASSWORD"),
            image_name=os.getenv("TRAIN_IMAGE_NAME"),
            train_script=str(get_root_absolute_path() / "train_job/run.py"),
            model_id=str(model_id),
            share_dir=os.getenv("SHARE_DIR", None),
            python_path=get_python_path(),
            aws_access_key=(os.getenv("AWS_ACCESS_KEY", "")),
            aws_access_secret=(os.getenv("AWS_ACCESS_SECRET", "")),
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
            "user_id": str(model.user_id),
        },
    )


@train_router.post("/udt")
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
        print(f"Extra options for training: {model_options}")
    except ValidationError as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Invalid options format: " + str(e),
        )

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
    except Exception as err:
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(err),
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
            image_name=os.getenv("TRAIN_IMAGE_NAME"),
            train_script=str(get_root_absolute_path() / "train_job/run.py"),
            model_id=str(model_id),
            share_dir=os.getenv("SHARE_DIR", None),
            python_path=get_python_path(),
            aws_access_key=(os.getenv("AWS_ACCESS_KEY", "")),
            aws_access_secret=(os.getenv("AWS_ACCESS_SECRET", "")),
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
        session.commit()
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
