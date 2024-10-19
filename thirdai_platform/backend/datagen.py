import os
import traceback
from pathlib import Path
from typing import List, Optional

from backend.utils import (
    get_platform,
    get_python_path,
    model_bazaar_path,
    submit_nomad_job,
    thirdai_platform_dir,
)
from database import schema
from database.session import get_session
from fastapi import Depends, status
from platform_common.pydantic_models.training import (
    DatagenOptions,
    JobOptions,
    LabelEntity,
    LLMProvider,
    UDTSubType,
)
from platform_common.thirdai_storage.data_types import TokenClassificationData
from platform_common.utils import response, save_dict
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session


def get_catalogs(task: schema.UDT_Task, session: Session):
    return session.query(schema.Catalog).filter(schema.Catalog.task == task).all()


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


def dump_generation_args(path: str, args: BaseModel):
    os.makedirs(path, exist_ok=True)
    save_dict(
        os.path.join(path, "generation_args.json"),
        **args.model_dump(),
    )


def generate_data_for_train_job(
    data_id: str,
    secret_token: str,
    license_key: str,
    options: DatagenOptions,
    job_options: JobOptions,
):
    options_dict = options.datagen_options.model_dump()
    del options_dict["sub_type"]
    if options.datagen_options.sub_type == UDTSubType.text:
        generate_text_data(
            task_prompt=options.task_prompt,
            data_id=data_id,
            secret_token=secret_token,
            license_key=license_key,
            llm_provider=options.llm_provider,
            datagen_options=TextClassificationGenerateArgs(**options_dict),
            job_options=job_options,
        )
    else:
        generate_token_data(
            task_prompt=options.task_prompt,
            data_id=data_id,
            secret_token=secret_token,
            license_key=license_key,
            llm_provider=options.llm_provider,
            datagen_options=TokenClassificationGenerateArgs(**options_dict),
            job_options=job_options,
        )


class TextClassificationGenerateArgs(BaseModel):
    samples_per_label: int
    target_labels: List[LabelEntity]
    user_vocab: Optional[List[str]] = None
    user_prompts: Optional[List[str]] = None
    vocab_per_sentence: int = 4


def generate_text_data(
    task_prompt: str,
    data_id: str,
    secret_token: str,
    license_key: str,
    llm_provider: LLMProvider,
    datagen_options: TextClassificationGenerateArgs,
    job_options: JobOptions,
):
    try:
        extra_options = JobOptions.model_validate(job_options).model_dump()
        extra_options = {k: v for k, v in extra_options.items() if v is not None}
        if extra_options:
            print(f"Extra options for training: {extra_options}")
    except ValidationError as e:
        raise ValueError(f"Invalid extra options format: {e}")

    extra_options["secret_token"] = secret_token

    genai_key = os.getenv("GENAI_KEY")
    if genai_key is None:
        raise ValueError(f"Need gen_ai key for data-generation")

    # Dump the datagen option in the storage dir
    storage_dir = os.path.join(model_bazaar_path(), "generated_data", str(data_id))
    dump_generation_args(storage_dir, datagen_options)

    try:
        nomad_response = submit_nomad_job(
            str(
                Path(os.getcwd())
                / "backend"
                / "nomad_jobs"
                / "generate_data_job.hcl.j2"
            ),
            nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
            platform=get_platform(),
            tag=os.getenv("TAG"),
            registry=os.getenv("DOCKER_REGISTRY"),
            docker_username=os.getenv("DOCKER_USERNAME"),
            docker_password=os.getenv("DOCKER_PASSWORD"),
            image_name=os.getenv("DATA_GENERATION_IMAGE_NAME"),
            thirdai_platform_dir=thirdai_platform_dir(),
            generate_script="data_generation_job.run",
            task_prompt=task_prompt,
            data_id=data_id,
            storage_dir=storage_dir,
            data_category="text",
            llm_provider=llm_provider.value,
            model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT", None),
            share_dir=os.getenv("SHARE_DIR", None),
            genai_key=os.getenv("GENAI_KEY", None),
            license_key=license_key,
            extra_options=extra_options,
            python_path=get_python_path(),
        )
        nomad_response.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Failed to generate data. {e}")


class TokenClassificationGenerateArgs(BaseModel):
    tags: List[LabelEntity]
    num_sentences_to_generate: int
    num_samples_per_tag: Optional[int] = None
    allocation_cores: Optional[int] = None
    allocation_memory: Optional[int] = None

    # example NER samples
    samples: Optional[List[TokenClassificationData]] = None
    templates_per_sample: int = 10


def generate_token_data(
    task_prompt: str,
    data_id: str,
    secret_token: str,
    license_key: str,
    llm_provider: LLMProvider,
    datagen_options: TokenClassificationGenerateArgs,
    job_options: JobOptions,
):
    try:
        extra_options = JobOptions.model_validate(job_options).model_dump()
        extra_options = {k: v for k, v in extra_options.items() if v is not None}
        if extra_options:
            print(f"Extra options for training: {extra_options}")
    except ValidationError as e:
        raise ValueError(f"Invalid extra options format: {e}")

    extra_options["secret_token"] = secret_token
    genai_key = os.getenv("GENAI_KEY")
    if genai_key is None:
        raise ValueError(f"Need gen_ai key for data-generation")

    # Dump the datagen option in the storage dir
    storage_dir = os.path.join(model_bazaar_path(), "generated_data", str(data_id))
    dump_generation_args(storage_dir, datagen_options)

    try:
        nomad_response = submit_nomad_job(
            str(
                Path(os.getcwd())
                / "backend"
                / "nomad_jobs"
                / "generate_data_job.hcl.j2"
            ),
            nomad_endpoint=os.getenv("NOMAD_ENDPOINT"),
            platform=get_platform(),
            tag=os.getenv("TAG"),
            registry=os.getenv("DOCKER_REGISTRY"),
            docker_username=os.getenv("DOCKER_USERNAME"),
            docker_password=os.getenv("DOCKER_PASSWORD"),
            image_name=os.getenv("DATA_GENERATION_IMAGE_NAME"),
            thirdai_platform_dir=thirdai_platform_dir(),
            generate_script="data_generation_job.run",
            task_prompt=task_prompt,
            data_id=str(data_id),
            storage_dir=storage_dir,
            data_category="token",
            llm_provider=llm_provider.value,
            model_bazaar_endpoint=os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT", None),
            share_dir=os.getenv("SHARE_DIR", None),
            genai_key=genai_key,
            license_key=license_key,
            extra_options=extra_options,
            python_path=get_python_path(),
        )
        nomad_response.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Failed to generate data. {e}")


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
