from dotenv import load_dotenv

load_dotenv()

import argparse
import os
import sys

import boto3
from botocore import UNSIGNED
from botocore.client import Config
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

from headless import add_basic_args
from headless.dag_executor import DAGExecutor
from headless.functions import functions_registry, initialize_flow


def download_from_s3_if_not_exists(s3_uri, local_dir):
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)

    config = Config(
        signature_version=UNSIGNED,
        retries={"max_attempts": 10, "mode": "standard"},
        connect_timeout=5,
        read_timeout=60,
    )

    s3 = boto3.client("s3", config=config)
    bucket_name = s3_uri.split("/")[2]
    s3_path = "/".join(s3_uri.split("/")[3:])

    try:
        for key in s3.list_objects_v2(Bucket=bucket_name, Prefix=s3_path)["Contents"]:
            local_file_path = os.path.join(local_dir, key["Key"].split("/")[-1])
            if not os.path.exists(local_file_path):
                s3.download_file(bucket_name, key["Key"], local_file_path)
                print(f"Downloaded {local_file_path}")
    except (NoCredentialsError, PartialCredentialsError) as e:
        print(f"Error in downloading from S3: {str(e)}")
        sys.exit(1)


def normalize_s3_uri(s3_uri):
    return s3_uri.rstrip("/")


def main():
    parser = argparse.ArgumentParser(description="Run DAG-based test suite.")
    add_basic_args(parser)
    parser.add_argument(
        "--dag-file",
        type=str,
        help="Path to the DAG YAML file",
        default=os.path.join(os.path.dirname(__file__), "dag_config.yaml"),
    )
    parser.add_argument("--dag", type=str, help="Name of the DAG to run")
    parser.add_argument(
        "--task", type=str, help="Name of the individual task to run within the DAG"
    )
    parser.add_argument("--all", action="store_true", help="Run all DAGs")
    parser.add_argument("--run-name", type=str, required=True, help="Name of the run")
    parser.add_argument("--sharded", action="store_true", help="Run sharded training")

    args = parser.parse_args()
    additional_variables = {
        "sharded": args.sharded,
        "run_name": args.run_name,
    }

    local_test_dir = os.getenv("SHARE_DIR")
    if not local_test_dir:
        print("Error: SHARE_DIR environment variable is not set.")
        sys.exit(1)

    s3_uris = [
        "s3://thirdai-corp-public/ThirdAI-Enterprise-Test-Data/scifact",
        "s3://thirdai-corp-public/ThirdAI-Enterprise-Test-Data/clinc",
        "s3://thirdai-corp-public/ThirdAI-Enterprise-Test-Data/token",
    ]

    for s3_uri in s3_uris:
        normalized_uri = normalize_s3_uri(s3_uri)
        folder_name = normalized_uri.split("/")[-1]

        download_from_s3_if_not_exists(
            s3_uri, os.path.join(local_test_dir, folder_name)
        )

    dag_executor = DAGExecutor(
        function_registry=functions_registry, global_vars=additional_variables
    )
    dag_executor.load_dags_from_file(args.dag_file)

    initialize_flow(args.base_url, args.email, args.password)

    if args.all:
        dag_executor.execute_all()
    elif args.dag and args.task:
        dag_executor.execute_task(args.dag, args.task)
    elif args.dag:
        dag_executor.execute_dag(args.dag)
    else:
        print("Please specify either --dag, --task, or --all")
        sys.exit(1)


if __name__ == "__main__":
    main()
