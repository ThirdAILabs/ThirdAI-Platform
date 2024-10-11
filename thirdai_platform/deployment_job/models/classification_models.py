from abc import abstractmethod
from typing import Optional

from models.model import Model
from platform_common.pydantic_models.training import DeploymentConfig
from pydantic_models import inputs
from thirdai import bolt


class ClassificationModel(Model):
    def __init__(self, config: DeploymentConfig):
        super().__init__(config=config)
        self.model: bolt.UniversalDeepTransformer = self.load()

    def get_udt_path(self, model_id: Optional[str] = None) -> str:
        model_id = model_id or self.config.model_id
        return str(self.get_model_dir(model_id) / "model.udt")

    def load(self):
        return bolt.UniversalDeepTransformer.load(
            self.get_udt_path(self.config.model_id)
        )

    def save(self, model_id):
        self.model.save(self.get_udt_path(model_id))

    @abstractmethod
    def predict(self, **kwargs):
        pass


class TextClassificationModel(ClassificationModel):
    def __init__(self, config: DeploymentConfig):
        super().__init__(config=config)
        self.num_classes = self.model.predict({"text": "test"}).shape[-1]

    def predict(self, text: str, top_k: int, **kwargs):
        top_k = min(top_k, self.num_classes)
        prediction = self.model.predict({"text": text}, top_k=top_k)
        predicted_classes = [
            (self.model.class_name(class_id), activation)
            for class_id, activation in zip(*prediction)
        ]

        return inputs.SearchResultsTextClassification(
            query_text=text,
            predicted_classes=predicted_classes,
        )


class TokenClassificationModel(ClassificationModel):
    def predict(self, text: str, **kwargs):
        predicted_tags = self.model.predict({"source": text}, top_k=1)
        predictions = []
        for predicted_tag in predicted_tags:
            predictions.append([x[0] for x in predicted_tag])

        return inputs.SearchResultsTokenClassification(
            query_text=text,
            tokens=text.split(),
            predicted_tags=predictions,
        )
