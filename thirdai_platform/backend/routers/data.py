import os
import traceback
import uuid
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from auth.jwt import AuthenticatedUser, verify_access_token
from backend.config import Entity, JobOptions
from backend.datagen import (
    TextClassificationGenerateArgs,
    TokenClassificationGenerateArgs,
    generate_text_data,
    generate_token_data,
)
from backend.utils import response
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, Form, status
from licensing.verify.verify_license import valid_job_allocation, verify_license
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

data_router = APIRouter()


def get_catalogs(task: schema.UDT_Task, session: Session):
    query = session.query(schema.Catalog).filter(schema.Catalog.task == task)
    catalogs: List[schema.Catalog] = query.all()
    return catalogs


def find_dataset(
    catalogs: List[schema.Catalog], target_labels: str, cut_off: float = 0.75
):
    def similarity(dataset_labels: List[str], target_labels: List[str]) -> float:
        if not dataset_labels:
            return 0.0
        match_count = len(set(dataset_labels) & set(target_labels))
        return match_count / len(dataset_labels)

    most_suited_dataset = None
    max_similarity = -1
    for catalog in catalogs:
        if len(catalog.target_labels) >= len(target_labels):
            sim = similarity(catalog.target_labels, target_labels)
            if sim >= cut_off and sim > max_similarity:
                max_similarity = sim
                most_suited_dataset = catalog

    return most_suited_dataset


# Not sure if this will lead to exposure of using openai to generate data
class LLMProvider(str, Enum):
    openai = "openai"
    cohere = "cohere"


@data_router.post("/generate-text-data")
def generate_text_data_endpoint(
    task_prompt: str,
    llm_provider: LLMProvider = LLMProvider.openai,
    datagen_form: str = Form(default="{}"),
    job_form: str = Form(default="{}"),
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    # TODO(Gautam): Only people from ThirdAI should be able to access this endpoint
    try:
        extra_options = JobOptions.model_validate_json(job_form).model_dump()
        datagen_options: TextClassificationGenerateArgs = (
            TextClassificationGenerateArgs.model_validate_json(datagen_form)
        )

        extra_options = {k: v for k, v in extra_options.items() if v is not None}
        if extra_options:
            print(f"Extra options for training: {extra_options}")
    except ValidationError as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Invalid option format\nDetails: {str(e)}",
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
                message=f"Resource limit reached, cannot allocate new jobs.",
            )
    except Exception as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"License is not valid. {str(e)}",
        )

    data_id = uuid.uuid4()
    generate_text_data(
        task_prompt=task_prompt,
        data_id=str(data_id),
        secret_token="",
        license_key=license_info["boltLicenseKey"],
        llm_provider=llm_provider,
        datagen_options=datagen_options,
        job_options=extra_options,
    )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully submitted the text-data generation job",
    )


@data_router.post("/generate-token-data")
def generate_token_data_endpoint(
    task_prompt: str,
    llm_provider: LLMProvider = LLMProvider.openai,
    datagen_form: str = Form(default="{}"),
    job_form: str = Form(default="{}"),
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    # TODO(Gautam): Only people from ThirdAI should be able to access this endpoint
    try:
        extra_options = JobOptions.model_validate_json(job_form).model_dump()
        datagen_options: TokenClassificationGenerateArgs = (
            TokenClassificationGenerateArgs.model_validate_json(datagen_form)
        )
        extra_options = {k: v for k, v in extra_options.items() if v is not None}
        if extra_options:
            print(f"Extra options for training: {extra_options}")
    except ValidationError as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Invalid option format\nDetails: {str(e)}",
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
                message=f"Resource limit reached, cannot allocate new jobs.",
            )
    except Exception as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"License is not valid. {str(e)}",
        )

    data_id = uuid.uuid4()
    generate_token_data(
        task_prompt=task_prompt,
        data_id=str(data_id),
        secret_token="",
        license_key=license_info["boltLicenseKey"],
        llm_provider=llm_provider,
        datagen_options=datagen_options,
        job_options=extra_options,
    )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully submitted the data-generation job",
    )


@data_router.post("/find-dataset")
def find_datasets(
    task: schema.UDT_Task,
    target_labels: List[str],
    session: Session = Depends(get_session),
):

    try:
        catalogs = get_catalogs(task=task, session=session)
        # Filtering catalogs based on the target_labels
        most_suited_dataset_catalog = find_dataset(
            catalogs, target_labels=target_labels
        )

        if most_suited_dataset_catalog:

            data = {
                "dataset_name": most_suited_dataset_catalog.name,
                "catalog_id": str(most_suited_dataset_catalog.id),
                "find_status": True,
                "num_samples": most_suited_dataset_catalog.num_generated_samples,
            }
            # TODO(Pratyush/Gautam) convert the existing JSON files to CSV
            # dataset location will be os.getenv("SHARE_DIR"), "datasets", "catalog_id", "train.csv"),

        if not most_suited_dataset_catalog:
            data = {
                "dataset_name": None,
                "catalog_id": None,
                "find_status": False,
                "num_samples": 0,
            }

        return response(
            status_code=status.HTTP_200_OK,
            message="Successfully retrieved the preview of the data",
            data=data,
        )

    except Exception as e:
        traceback.print_exc()
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="unable to find a sample text-dataset",
        )
