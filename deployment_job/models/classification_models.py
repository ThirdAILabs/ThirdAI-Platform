from abc import abstractmethod

from models.model import Model
from pydantic_models import inputs
from thirdai import bolt


class ClassificationModel(Model):
    def __init__(self):
        super().__init__()
        self.model_path = self.get_udt_path()
        self.model: bolt.UniversalDeepTransformer = self.load_model()

    def get_udt_path(self):
        return str(self.get_model_dir(self.general_variables.model_id) / "model.udt")

    def load_model(self):
        return bolt.UniversalDeepTransformer.load(self.model_path)

    @abstractmethod
    def predict(self, **kwargs):
        pass


class TextClassificationModel(ClassificationModel):
    def __init__(self):
        super().__init__()

    def predict(self, **kwargs):
        query = kwargs["query"]
        top_k = kwargs["top_k"]
        prediction = self.model.predict({"text": query}, top_k=top_k)
        class_names = [self.model.class_name(x) for x in prediction[0]]

        return inputs.SearchResultsTextClassification(
            query_text=query,
            class_names=class_names,
        )


class TokenClassificationModel(ClassificationModel):
    def __init__(self):
        super().__init__()

    def predict(self, **kwargs):
        query = kwargs["query"]
        top_k = kwargs["top_k"]

        predicted_tags = self.model.predict({"source": query}, top_k=top_k)
        predictions = []
        for predicted_tag in predicted_tags:
            predictions.append([x[0] for x in predicted_tag])

        return inputs.SearchResultsTokenClassification(
            query_text=query,
            tokens=query.split(),
            predicted_tags=predictions,
        )
