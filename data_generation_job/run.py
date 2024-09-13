import io
import json
import os
from dataclasses import asdict
from urllib.parse import urljoin

import requests
from utils import load_dict
from variables import DataCategory, GeneralVariables

# Load general variables from environment
general_variables: GeneralVariables = GeneralVariables.load_from_env()


def launch_train_job(file_location: str, udt_options: dict):
    try:
        api_url = general_variables.model_bazaar_endpoint
        headers = {"User-Agent": "Datagen job"}
        url = urljoin(
            api_url,
            f"api/train/datagen-callback?data_id={general_variables.data_id}&secret_token={general_variables.secret_token}",
        )
        data = {
            "file_info": json.dumps(
                {"supervised_files": [{"path": file_location, "location": "nfs"}]}
            ),
            "model_options": json.dumps(
                {"model_type": "udt", "udt_options": udt_options}
            ),
        }
        response = requests.request("post", url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exception:
        print(exception)
        raise exception


def main():
    """
    Main function to initialize and generate the data based on environment variables.
    """
    generation_arg_fp = os.path.join(
        general_variables.storage_dir, "generation_args.json"
    )
    if general_variables.data_category == DataCategory.text:
        from text_data_factory import TextDataFactory
        from variables import TextGenerationVariables

        factory = TextDataFactory()
        args = TextGenerationVariables.model_validate(load_dict(generation_arg_fp))

    else:
        from token_data_factory import TokenDataFactory
        from variables import TokenGenerationVariables

        factory = TokenDataFactory()
        args = TokenGenerationVariables.model_validate(load_dict(generation_arg_fp))

    dataset_config = factory.generate_data(
        general_variables.task_prompt, **args.to_dict()
    )

    if general_variables.data_category == DataCategory.text:
        udt_options = {
            "udt_sub_type": "text",
            "text_column": dataset_config["input_feature"],
            "label_column": dataset_config["target_feature"],
            "n_target_classes": len(dataset_config["target_labels"]),
        }
    else:
        udt_options = {
            "udt_sub_type": "token",
            "source_column": dataset_config["input_feature"],
            "target_column": dataset_config["target_feature"],
            "target_labels": dataset_config["target_labels"],
        }

    # launch_train_job(dataset_config["filepath"], udt_options)


if __name__ == "__main__":
    main()
