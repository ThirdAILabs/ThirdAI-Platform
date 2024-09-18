import argparse

from headless.utils import (
    fetch_job_definition,
    restart_nomad_job,
    stop_nomad_job,
    update_docker_image_version,
)

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description="Update Docker image version for a Nomad job."
    )
    parser.add_argument(
        "--version",
        type=str,
        required=True,
        help="The new version of the Docker image (e.g., 34.56.78.90)",
    )

    args = parser.parse_args()
    new_version = args.version

    model_bazaar_job = "modelbazaar"
    nomad_endpoint = "http://localhost:4646/"

    # Fetch the job definition
    definition = fetch_job_definition(
        job_id=model_bazaar_job, nomad_endpoint=nomad_endpoint
    )

    # Update the Docker image version
    new_definition = update_docker_image_version(
        job_definition=definition, new_version=new_version
    )

    # Stop the existing job
    stop_nomad_job(model_bazaar_job, nomad_endpoint=nomad_endpoint)

    # Restart the job with the new definition
    restart_nomad_job(nomad_endpoint, payload=new_definition)
