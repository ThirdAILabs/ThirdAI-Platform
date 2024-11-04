import logging
import traceback
import uuid
from typing import Dict, List

from auth.jwt import AuthenticatedUser, verify_access_token
from backend.datagen import generate_text_data, generate_token_data
from backend.utils import validate_license_info
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, Form, status
from platform_common.pydantic_models.training import JobOptions, LLMProvider
from platform_common.utils import response
from pydantic import ValidationError
from sqlalchemy.orm import Session

data_router = APIRouter()


# Utility function to validate and process generation jobs (for both text and token generation)
def validate_and_generate_data(
    task_prompt: str,
    llm_provider: LLMProvider,
    datagen_form: str,
    job_form: str,
    generate_func,  # Either generate_text_data or generate_token_data
):
    try:
        extra_options: Dict = JobOptions.model_validate_json(job_form).model_dump()
        datagen_options = generate_func.__annotations__[
            "datagen_options"
        ].model_validate_json(datagen_form)

        extra_options = {k: v for k, v in extra_options.items() if v is not None}
        if extra_options:
            logging.info(f"Extra options for job: {extra_options}")
    except ValidationError as e:
        message = f"Invalid option format\nDetails: {str(e)}"
        logging.error(message)
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=message,
        )

    license_info = validate_license_info()

    data_id = uuid.uuid4()

    # Call the appropriate data generation function (text or token)
    generate_func(
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


@data_router.post("/generate-text-data")
def generate_text_data_endpoint(
    task_prompt: str,
    llm_provider: LLMProvider = LLMProvider.openai,
    datagen_form: str = Form(default="{}"),
    job_form: str = Form(default="{}"),
    _: AuthenticatedUser = Depends(verify_access_token),
):
    return validate_and_generate_data(
        task_prompt=task_prompt,
        llm_provider=llm_provider,
        datagen_form=datagen_form,
        job_form=job_form,
        generate_func=generate_text_data,
    )


@data_router.post("/generate-token-data")
def generate_token_data_endpoint(
    task_prompt: str,
    llm_provider: LLMProvider = LLMProvider.openai,
    datagen_form: str = Form(default="{}"),
    job_form: str = Form(default="{}"),
    _: AuthenticatedUser = Depends(verify_access_token),
):
    return validate_and_generate_data(
        task_prompt=task_prompt,
        llm_provider=llm_provider,
        datagen_form=datagen_form,
        job_form=job_form,
        generate_func=generate_token_data,
    )


# Helper function to get the catalog of datasets
def get_catalogs(task: schema.UDT_Task, session: Session):
    # Fetch catalogs based on task type
    query = session.query(schema.Catalog).filter(schema.Catalog.task == task)
    catalogs: List[schema.Catalog] = query.all()
    return catalogs


# Helper function to find the most suited dataset
def find_dataset(
    catalogs: List[schema.Catalog], target_labels: List[str], cut_off: float = 0.75
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


# Dataset Finding Endpoint
@data_router.post("/find-dataset")
def find_datasets(
    task: schema.UDT_Task,
    target_labels: List[str],
    session: Session = Depends(get_session),
):
    try:
        # Fetch catalogs for the task
        catalogs = get_catalogs(task=task, session=session)

        # Find the best-suited dataset based on target labels
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
        else:
            data = {
                "dataset_name": None,
                "catalog_id": None,
                "find_status": False,
                "num_samples": 0,
            }

        return response(
            status_code=status.HTTP_200_OK,
            message="Successfully retrieved the preview of the dataset",
            data=data,
        )

    except Exception as e:
        logging.error(traceback.print_exc())
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Unable to find a suitable dataset: {e}",
        )
