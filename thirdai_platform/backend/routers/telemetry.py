import logging
import os

from backend.utils import get_platform, get_service_info, list_services
from fastapi import APIRouter, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from platform_common.utils import response

telemetry_router = APIRouter()


# TODO(Nicholas): how can we handle authentication for this endpoint
@telemetry_router.get("/deployment-services")
def deployment_services():
    nomad_endpoint = os.getenv("NOMAD_ENDPOINT")
    # Returns a json lists of targets for prometheus to scrape for deployment metrics.
    # https://prometheus.io/docs/prometheus/latest/configuration/configuration/#http_sd_config
    services_res = list_services(nomad_endpoint)

    if services_res.status_code != 200:
        logging.error(f"Unable to retrieve list of services from nomad")
        # TODO(Nicholas): Should this just return an empty list to avoid causing
        # errors for downstream metric scrapper?
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Unable to retrieve list of services from nomad.",
            success=False,
        )

    platform = get_platform()

    targets = []
    for service in services_res.json()[0]["Services"]:
        service_name: str = service["ServiceName"]
        if service_name.startswith("deployment"):
            service_info_res = get_service_info(nomad_endpoint, service_name)
            if service_info_res.status_code != 200:
                logging.error(
                    f"Unable to retrieve info for service {service_name}",
                )
                continue

            _, model_id = service_name.split("-", maxsplit=1)
            for allocation in service_info_res.json():
                if platform == "local":
                    address = f"http://host.docker.internal:{allocation['Port']}"
                else:
                    address = f"{allocation['Address']}:{allocation['Port']}"
                targets.append(
                    {
                        "targets": [address],
                        "labels": {
                            "model_id": model_id,
                            "alloc_id": allocation["AllocID"],
                            "node_id": allocation["NodeID"],
                            "address": address,
                        },
                    }
                )

    return JSONResponse(content=jsonable_encoder(targets))
