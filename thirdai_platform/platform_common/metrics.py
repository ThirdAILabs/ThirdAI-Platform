import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List

import pandas as pd


@dataclass
class PerTagMetrics:
    metrics: Dict[str, Dict[str, float]]
    true_positives: List[Dict[str, Any]]
    false_positives: List[Dict[str, Any]]
    false_negatives: List[Dict[str, Any]]


def calculate_ner_metrics(
    model,
    test_data: pd.DataFrame,
    source_col: str,
    target_col: str,
    samples_to_collect: int = 5,
) -> PerTagMetrics:
    """
    Calculate NER model performance metrics including precision, recall, and F1 score per tag.
    Also collects example samples for true positives, false positives, and false negatives.

    Args:
        model: The NER model that implements predict() and list_ner_tags() methods
        test_data: DataFrame containing test data
        source_col: Name of the source text column
        target_col: Name of the target labels column
        samples_to_collect: Number of example samples to collect for each metric

    Returns:
        PerTagMetrics containing metrics and example samples
    """
    true_positives = defaultdict(int)
    false_positives = defaultdict(int)
    false_negatives = defaultdict(int)

    true_positive_samples = defaultdict(list)
    false_positive_samples = defaultdict(list)
    false_negative_samples = defaultdict(list)

    for row in test_data.itertuples():
        source = getattr(row, source_col)
        target = getattr(row, target_col)

        preds = model.predict({source_col: source}, top_k=1)
        predictions = " ".join(p[0][0] for p in preds)
        labels = target.split()

        for i, (pred, label) in enumerate(zip(preds, labels)):
            tag = pred[0][0]
            if tag == label:
                true_positives[label] += 1
                if len(true_positive_samples[label]) < samples_to_collect:
                    true_positive_samples[label].append(
                        {
                            "source": source,
                            "target": target,
                            "predictions": predictions,
                            "index": i,
                        }
                    )
            else:
                false_positives[tag] += 1
                if len(false_positive_samples[tag]) < samples_to_collect:
                    false_positive_samples[tag].append(
                        {
                            "source": source,
                            "target": target,
                            "predictions": predictions,
                            "index": i,
                        }
                    )
                false_negatives[label] += 1
                if len(false_negative_samples[label]) < samples_to_collect:
                    false_negative_samples[label].append(
                        {
                            "source": source,
                            "target": target,
                            "predictions": predictions,
                            "index": i,
                        }
                    )

    metric_summary = {}
    for tag in model.list_ner_tags():
        if tag == "O":
            continue

        tp = true_positives[tag]

        if tp + false_positives[tag] == 0:
            precision = float("nan")
        else:
            precision = tp / (tp + false_positives[tag])

        if tp + false_negatives[tag] == 0:
            recall = float("nan")
        else:
            recall = tp / (tp + false_negatives[tag])

        if precision + recall == 0:
            fmeasure = float("nan")
        else:
            fmeasure = 2 * precision * recall / (precision + recall)

        metric_summary[tag] = {
            "precision": "NaN" if math.isnan(precision) else round(precision, 3),
            "recall": "NaN" if math.isnan(recall) else round(recall, 3),
            "fmeasure": "NaN" if math.isnan(fmeasure) else round(fmeasure, 3),
        }

    def remove_null_tag(samples: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in samples.items() if k != "O"}

    return PerTagMetrics(
        metrics=metric_summary,
        true_positives=remove_null_tag(true_positive_samples),
        false_positives=remove_null_tag(false_positive_samples),
        false_negatives=remove_null_tag(false_negative_samples),
    )
