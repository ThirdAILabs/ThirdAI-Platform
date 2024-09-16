import os

import requests
import yaml
from variables import GeneralVariables

# Load general variables from environment
general_variables: GeneralVariables = GeneralVariables.load_from_env()


def run():
    if general_variables.platform == "local":
        targets = ["host.docker.internal:4646"]
    else:
        nomad_url = (
            f"{general_variables.model_bazaar_endpoint.rstrip('/')}:4646/v1/nodes"
        )

        # Fetch the node data from Nomad
        headers = {"X-Nomad-Token": general_variables.management_token}
        response = requests.get(nomad_url, headers=headers)
        nodes = response.json()

        targets = [f"{node['Address']}:4646" for node in nodes]

    # Prometheus template
    prometheus_config = {
        "global": {
            "scrape_interval": "1s",
            "external_labels": {"env": "dev", "cluster": "local"},
        },
        "scrape_configs": [
            {
                "job_name": "nomad-agent",
                "metrics_path": "/v1/metrics?format=prometheus",
                "static_configs": [{"targets": targets, "labels": {"role": "agent"}}],
                "relabel_configs": [
                    {
                        "source_labels": ["__address__"],
                        "regex": "([^:]+):.+",
                        "target_label": "hostname",
                        "replacement": "nomad-agent-$1",
                    }
                ],
            }
        ],
    }
    os.makedirs(os.path.dirname(general_variables.promfile), exist_ok=True)

    with open(general_variables.promfile, "w") as file:
        yaml.dump(prometheus_config, file, sort_keys=False)

    print(f"Prometheus configuration has been written to {general_variables.promfile}")


if __name__ == "__main__":
    run()
