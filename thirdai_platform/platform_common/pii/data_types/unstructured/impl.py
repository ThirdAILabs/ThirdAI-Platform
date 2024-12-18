from typing import List, Tuple

from platform_common.pii.data_types.base import DataType
from platform_common.pii.data_types.pydantic_models import (
    UnstructuredTokenClassificationResults,
)


class UnstructuredText(DataType):
    def __init__(self, log: str):
        self._inference_sample = {"source": log}

    def process_prediction(self, model_predictions: List[List[Tuple[str, float]]]):
        predictions = []
        for prediction in model_predictions:
            predictions.append([x[0] for x in prediction])

        tokens = self._inference_sample["source"].split()

        if len(predictions) != len(tokens):
            raise ValueError(
                "Error parsing input text, this is likely because the input contains unsupported unicode characters."
            )

        return UnstructuredTokenClassificationResults(
            data_type="unstructured",
            query_text=self._inference_sample["source"],
            tokens=tokens,
            predicted_tags=predictions,
        )

    @property
    def inference_sample(self):
        return self._inference_sample
