from logging import Logger
from urllib.parse import urljoin

import requests
from deployment_job.permissions import Permissions
from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from guardrail import Guardrail, LabelMap
from platform_common.pydantic_models.deployment import DeploymentConfig
from platform_common.utils import response
from prometheus_client import Summary
from pydantic_models import inputs
from reporter import Reporter

query_metric = Summary("enterprise_search_query", "Enterprise Search Queries")


class EnterpriseSearchRouter:
    def __init__(self, config: DeploymentConfig, reporter: Reporter, logger: Logger):
        self.config = config
        self.logger = logger

        self.retrieval_endpoint = urljoin(
            self.config.model_bazaar_endpoint,
            self.config.model_options.retrieval_id + "/",
        )
        self.logger.info(f"Retrieval endpoint set to {self.retrieval_endpoint}")

        if self.config.model_options.guardrail_id:
            self.guardrail = Guardrail(
                guardrail_model_id=self.config.model_options.guardrail_id,
                model_bazaar_endpoint=self.config.model_bazaar_endpoint,
            )
            self.logger.info(
                f"Guardrail initialized with ID {self.config.model_options.guardrail_id}"
            )
        else:
            self.guardrail = None
            self.logger.info("No guardrail configuration found for this model")

        self.router = APIRouter()
        self.router.add_api_route("/search", self.search, methods=["POST"])
        self.router.add_api_route("/unredact", self.unredact, methods=["POST"])

    @query_metric.time()
    def search(
        self,
        params: inputs.NDBSearchParams,
        token: str = Depends(Permissions.verify_permission("read")),
    ):
        res = requests.post(
            url=urljoin(self.retrieval_endpoint, "search"),
            json=params.model_dump(),
            headers={
                "Authorization": f"Bearer {token}",
            },
        )
        if res.status_code != status.HTTP_200_OK:
            self.logger.error(
                f"Failed retrieval request with status code {res.status_code}",
                extra={"response": res.text},
            )
            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Unable to get resutls from retrieval model: " + str(res),
            )

        results = inputs.EnterpriseSearchResults.model_validate(res.json()["data"])

        if self.guardrail:
            label_map = LabelMap()

            results.query_text = self.guardrail.redact_pii(
                text=results.query_text, access_token=token, label_map=label_map
            )

            for ref in results.references:
                ref.text = self.guardrail.redact_pii(
                    text=ref.text, access_token=token, label_map=label_map
                )
            results.pii_entities = label_map.get_entities()
            self.logger.info(
                "Redacted PII from search results",
                extra={"pii_entities": results.pii_entities},
            )

        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=jsonable_encoder(results),
        )

    def unredact(
        self,
        args: inputs.UnredactArgs,
        token: str = Depends(Permissions.verify_permission("read")),
    ):
        if self.guardrail:
            unredacted_text = self.guardrail.unredact_pii(args.text, args.pii_entities)
            self.logger.info(
                "Unredacted text successfully",
                extra={"unredacted_text": unredacted_text},
            )
            return response(
                status_code=status.HTTP_200_OK,
                message="Successful",
                data={"unredacted_text": unredacted_text},
            )
        else:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Cannot unredact text since this model was not configured with guardrails.",
            )
