from argparse import ArgumentParser

from azure_provider import AzureProvider
from docker_constants import image_base_names
from utils import image_name_for_branch, load_config

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "-b",
        "--branch",
        required=True,
        help="The branch to delete docker images from to. E.g. 'prod', 'test', etc.",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the YAML configuration file. Defaults to 'config.yaml' in the current directory if not specified.",
    )
    parser.add_argument(
        "--version",
        type=str,
        required=True,
        help="Delete the docker images of this version for the provided branch.",
    )
    parser.add_argument(
        "--client_id",
        required=True,
        type=str,
    )
    parser.add_argument(
        "--tenant_id",
        type=str,
        required=True,
    )
    parser.add_argument(
        "--secret",
        type=str,
        required=True,
    )
    args = parser.parse_args()
    tag = "v" + args.version
    config = load_config(args.config)
    provider = AzureProvider(config["azure"]["registry"])
    for image in image_base_names.to_list():
        provider.delete_image(
            image_name_for_branch(image, args.branch),
            tag,
            tenant_id=args.tenant_id,
            client_id=args.client_id,
            client_secret=args.secret,
        )
