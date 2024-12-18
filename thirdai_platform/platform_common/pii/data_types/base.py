from abc import ABC, abstractmethod


class DataType(ABC):
    @abstractmethod
    def process_prediction(self, model_predictions: str):
        pass

    @property
    @abstractmethod
    def inference_sample(self):
        pass
