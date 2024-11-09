from typing import Any, Dict, List

from pydantic import BaseModel


class PerTagMetrics(BaseModel):
    metrics: Dict[str, Dict[str, float]]

    true_positives: List[Dict[str, Any]]
    false_positives: List[Dict[str, Any]]
    false_negatives: List[Dict[str, Any]]


class Throughput(BaseModel):
    token_throughput: float = None
    sample_throughput: float = None


class ModelMetrics(BaseModel):
    per_tag_metrics: PerTagMetrics = None
    throughput: Throughput = None
