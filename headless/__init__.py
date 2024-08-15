import argparse


def add_basic_args(parser: argparse.ArgumentParser):
    """
    Add basic arguments to the provided argument parser.

    Parameters:
    parser (argparse.ArgumentParser): The argument parser to which the arguments will be added.

    Arguments added:
    --base-url (str): The API URL of the local application, e.g., http://127.0.0.1:80/api/.
                      This argument is required.
    --email (str): The email address used for authentication. This argument is required.
    --password (str): The password used for authentication. This argument is required.
    """
    parser.add_argument(
        "--base-url",
        type=str,
        required=True,
        help="The api url of the local application like http://127.0.0.1:80/api/.",
    )
    parser.add_argument("--email", type=str, required=True)
    parser.add_argument("--password", type=str, required=True)
