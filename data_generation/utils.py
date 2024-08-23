import csv
import json
import random
import re
from typing import Dict, List


def save_dict(write_to: str, **kwargs):
    with open(write_to, "w") as fp:
        json.dump(kwargs, fp, indent=4)


def assert_sufficient_examples(
    target_labels: List[str], examples: Dict[str, List[str]]
):
    missing_examples = [label for label in target_labels if label not in examples]
    if missing_examples:
        raise ValueError(
            f"Examples are not given for all labels. Labels with missing examples: {', '.join(missing_examples)}"
        )


def assert_sufficient_descriptions(
    target_labels: List[str], labels_description: Dict[str, str]
):
    missing_description = [
        label for label in target_labels if label not in labels_description
    ]
    if missing_description:
        raise ValueError(
            f"Descriptions are not given for all labels. Labels with missing descriptions: {', '.join(missing_description)}"
        )


def subsample_dictionary(data: Dict[str, List[str]], k=2):
    return {
        key: random.sample(values, min(k, len(values))) for key, values in data.items()
    }
