from urllib.parse import urljoin

import requests
from config import DeploymentConfig
from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from guardrail import Guardrail, LabelMap
from permissions import Permissions
from prometheus_client import Summary
from pydantic_models import inputs
from reporter import Reporter
from utils import propagate_error, response

query_metric = Summary("enterprise_search_query", "Enterprise Search Queries")


class EnterpriseSearchRouter:
    def __init__(self, config: DeploymentConfig, reporter: Reporter):
        self.config = config

        self.retrieval_endpoint = urljoin(
            self.config.model_bazaar_endpoint,
            self.config.model_options.retrieval_id + "/",
        )

        if self.config.model_options.guardrail_id:
            self.guardrail = Guardrail(
                guardrail_model_id=self.config.model_options.guardrail_id,
                model_bazaar_endpoint=self.config.model_bazaar_endpoint,
            )
        else:
            self.guardrail = None

        self.router = APIRouter()
        self.router.add_api_route("/search", self.search, methods=["POST"])
        self.router.add_api_route("/unredact", self.unredact, methods=["POST"])

    @query_metric.time()
    @propagate_error
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

        return response(
            status_code=status.HTTP_200_OK,
            message="Successful",
            data=jsonable_encoder(results),
        )

    @propagate_error
    def unredact(
        self,
        args: inputs.UnredactArgs,
        token: str = Depends(Permissions.verify_permission("read")),
    ):
        if self.guardrail:
            unredacted_text = self.guardrail.unredact_pii(args.text, args.pii_entities)
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
