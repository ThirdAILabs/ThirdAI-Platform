import re
from collections import defaultdict
from typing import Dict, List
from urllib.parse import urljoin

import requests
from fastapi import HTTPException, status


class LabelMap:
    def __init__(self):
        self.tag_to_entities = defaultdict(dict)
        self.next_label = 0

        self.decode_re = re.compile(r"\[([A-Z]+) #(\d+)\]")

    def get_label(self, tag: str, entity: str) -> str:
        for label, existing_entity in self.tag_to_entities[tag].items():
            if entity == existing_entity or max_overlap(entity, existing_entity) > 5:
                return label

        label = f"[{tag} #{self.next_label}]"
        self.next_label += 1

        self.tag_to_entities[tag][label] = entity
        return label


class Guardrail:
    def __init__(self, guardrail_model_id: str, model_bazaar_endpoint: str):
        self.endpoint = urljoin(model_bazaar_endpoint, f"{guardrail_model_id}/predict")

    def query_pii_model(self, text: str, access_token: str):
        res = requests.post(
            self.endpoint,
            headers={
                "User-Agent": "NDB Deployment job",
                "Authorization": f"Bearer {access_token}",
            },
            json={"text": text, "top_k": 1},
        )

        if res.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unable to access guardrail model: error {res.status_code}",
            )

        return res.json()["data"]

    def redact_pii(self, text: str, access_token: str, label_map: LabelMap):
        data = self.query_pii_model(text=text, access_token=access_token)

        entities, tags = merge_tags(tokens=data["tokens"], tags=data["predicted_tags"])

        entities = [
            label_map.get_label(tag=tag, entity=entity) if tag != "O" else entity
            for entity, tag in zip(entities, tags)
        ]

        return " ".join(entities)

    def unredact_pii(self, redacted_text: str, entity_map: Dict[str, Dict[str, str]]):
        def replace(match):
            tag = match[1]
            if tag in entity_map:
                return entity_map[tag].get(match[0], "[UNKNOWN ENTITY]")
            return "[UNKNOWN ENTITY]"

        return re.sub(r"\[([A-Z]+) #(\d+)\]", replace, redacted_text)


def max_overlap(a: str, b: str) -> int:
    def longest_prefix(i: int, j: int) -> int:
        cnt = 0
        for k in range(0, min(len(a) - i, len(b) - j)):
            if a[i + k] == b[j + k]:
                cnt += 1
            else:
                break
        return cnt

    return max(longest_prefix(i, j) for i in range(len(a)) for j in range(len(b)))


def merge_tags(tokens: List[str], tags: List[List[str]]):
    merged_tokens = []
    merged_tags = []

    index = 0
    while index < len(tokens):
        start = index
        curr_tag = tags[index][0]

        while index < len(tokens) and tags[index][0] == curr_tag:
            index += 1

        merged_tokens.append(" ".join(tokens[start:index]))
        merged_tags.append(curr_tag)

    return merged_tokens, merged_tags
