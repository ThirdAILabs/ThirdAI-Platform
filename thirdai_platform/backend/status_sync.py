import logging
import os

from backend.utils import get_nomad_job
from database import schema
from database.session import get_session
from fastapi_utils.tasks import repeat_every


@repeat_every(seconds=5)
async def sync_job_statuses() -> None:
    """
    Syncs status of nomad jobs with internal database. This is useful for cases
    when jobs fail before we're able to catch the issue and update the database.
    """

    session = next(get_session())

    try:
        models: list[schema.Model] = session.query(schema.Model).all()

        for model in models:
            if (
                model.train_status == schema.Status.starting
                or model.train_status == schema.Status.in_progress
            ):
                # TODO support sharded models
                model_data = get_nomad_job(
                    model.get_train_job_name(), os.getenv("NOMAD_ENDPOINT")
                )
                if not model_data or model_data["Status"] == "dead":
                    logging.warning(
                        f"Model {model.id} train status was starting or in_progress but the nomad"
                        "job is either dead or not found. Setting status to failed."
                    )
                    model.train_status = schema.Status.failed

            deployment_data = get_nomad_job(
                model.get_deployment_name(), os.getenv("NOMAD_ENDPOINT")
            )
            if (
                model.deploy_status == schema.Status.starting
                or model.deploy_status == schema.Status.in_progress
            ):
                if not deployment_data or deployment_data["Status"] == "dead":
                    logging.warning(
                        f"Model {model.id} deployment status was starting or in_progress but the nomad"
                        "job is either dead or not found. Setting status to failed."
                    )
                    model.deploy_status = schema.Status.failed

            if model.deploy_status == schema.Status.complete:
                if not deployment_data or deployment_data["Status"] == "dead":
                    logging.warning(
                        f"Model {model.id} deployment status was complete but the nomad"
                        "job is either dead or not found. Setting status to stopped instead."
                    )
                    model.deploy_status = schema.Status.stopped

        session.commit()
    finally:
        session.close()
