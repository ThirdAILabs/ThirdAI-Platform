import json
from urllib.parse import urljoin

import requests
from data_generation_job.variables import DataCategory, GeneralVariables
from platform_common.utils import load_dict

# Load general variables from environment
general_variables: GeneralVariables = GeneralVariables.load_from_env()


def launch_train_job(dataset_config: dict, udt_options: dict):
    try:
        api_url = general_variables.model_bazaar_endpoint
        headers = {"User-Agent": "Datagen job"}
        url = urljoin(
            api_url,
            f"api/train/datagen-callback?data_id={general_variables.data_id}&secret_token={general_variables.secret_token}",
        )
        data = {
            "file_info": json.dumps(
                {
                    "supervised_files": [
                        {"path": dataset_config["filepath"], "location": "nfs"}
                    ]
                }
                if dataset_config["train_samples"] > 0
                else {"supervised_files": []}
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
    import os

    generation_arg_fp = os.path.join(
        general_variables.storage_dir, "generation_args.json"
    )
    if general_variables.data_category == DataCategory.text:
        from data_generation_job.text_data_factory import TextDataFactory
        from data_generation_job.variables import TextGenerationVariables

        factory = TextDataFactory()
        args = TextGenerationVariables.model_validate(load_dict(generation_arg_fp))

    else:
        from data_generation_job.token_data_factory import TokenDataFactory
        from data_generation_job.variables import TokenGenerationVariables

        factory = TokenDataFactory()
        args = TokenGenerationVariables.model_validate(load_dict(generation_arg_fp))
        common_patterns = args.find_common_patterns()
        args.remove_common_patterns()

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
            "target_labels": dataset_config["target_labels"] + common_patterns,
        }

    if general_variables.secret_token:
        launch_train_job(dataset_config, udt_options)


if __name__ == "__main__":
    main()
