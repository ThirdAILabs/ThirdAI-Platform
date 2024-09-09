from abc import abstractmethod
from typing import Optional

from models.model import Model
from pydantic_models import inputs
from thirdai import bolt


class ClassificationModel(Model):
    def __init__(
        self, model_id: Optional[str] = None, model_path: Optional[str] = None
    ):
        super().__init__()
        if model_path:
            self.model_path = model_path
        else:
            self.model_path = self.get_udt_path(model_id)
        self.model: bolt.UniversalDeepTransformer = self.load()

    def get_udt_path(self, model_id: Optional[str] = None) -> str:
        model_id = model_id or self.general_variables.model_id
        return str(self.get_model_dir(model_id) / "model.udt")

    def load(self):
        return bolt.UniversalDeepTransformer.load(self.model_path)

    def save(self, model_id):
        self.model.save(self.get_udt_path(model_id))

    @abstractmethod
    def predict(self, **kwargs):
        pass


class TextClassificationModel(ClassificationModel):
    def __init__(
        self, model_id: Optional[str] = None, model_path: Optional[str] = None
    ):
        super().__init__(model_id, model_path)
        self.num_classes = self.model.predict({"text": "test"}).shape[-1]

    def predict(self, **kwargs):
        query = kwargs["query"]
        top_k = min(kwargs["top_k"], self.num_classes)
        prediction = self.model.predict({"text": query}, top_k=top_k)
        predicted_classes = [
            (self.model.class_name(class_id), activation)
            for class_id, activation in zip(*prediction)
        ]

        self.reporter.log(
            action="predict",
            model_id=self.general_variables.model_id,
            access_token=kwargs.get("token"),
            train_samples=[
                {
                    "query": query,
                    "top_k": str(top_k),
                    "predicted_classes": ",".join(
                        [class_name for class_name, _ in predicted_classes]
                    ),
                }
            ],
        )

        return inputs.SearchResultsTextClassification(
            query_text=query,
            predicted_classes=predicted_classes,
        )


class TokenClassificationModel(ClassificationModel):
    def __init__(
        self, model_id: Optional[str] = None, model_path: Optional[str] = None
    ):
        super().__init__(model_id, model_path)

    def predict(self, **kwargs):
        query = kwargs["query"]

        predicted_tags = self.model.predict({"source": query}, top_k=1)
        predictions = []
        for predicted_tag in predicted_tags:
            predictions.append([x[0] for x in predicted_tag])

        self.reporter.log(
            action="predict",
            model_id=self.general_variables.model_id,
            access_token=kwargs.get("token"),
            train_samples=[{"query": query, "predictions": ",".join(predictions[0])}],
        )

        return inputs.SearchResultsTokenClassification(
            query_text=query,
            tokens=query.split(),
            predicted_tags=predictions,
        )
