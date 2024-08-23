import os
from dataclasses import asdict

from utils import save_dict
from variables import DataCategory, GeneralVariables

# Load general variables from environment
general_variables: GeneralVariables = GeneralVariables.load_from_env()


def main():
    """
    Main function to initialize and generate the data based on environment variables.
    """
    if general_variables.data_category == DataCategory.text:
        from text_data_factory import TextDataFactory
        from variables import TextGenerationVariables

        factory = TextDataFactory()
        args = TextGenerationVariables.load_from_env()

    else:
        from token_data_factory import TokenDataFactory
        from variables import TokenGenerationVariables

        factory = TokenDataFactory()
        args = TokenGenerationVariables.load_from_env()

    # Saving the args first
    save_dict(
        factory.generation_args_location,
        **{"data_id": general_variables.data_id, **asdict(args)}
    )
    dataset_config = factory.generate_data(**asdict(args))


if __name__ == "__main__":
    main()
