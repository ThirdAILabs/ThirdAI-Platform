from platform_common.pii.data_types.pydantic_models import (
    UnstructuredTokenClassificationResults,
    XMLTokenClassificationResults,
)
from platform_common.pii.data_types.unstructured import UnstructuredText
from platform_common.pii.data_types.xml import XMLLog


def convert_log_to_concrete_type(log: str):
    try:
        return XMLLog(log)
    except:
        return UnstructuredText(log)


__all__ = [
    "DataType",
    "UnstructuredText",
    "XMLLog",
    "XMLTokenClassificationResults",
    "UnstructuredTokenClassificationResults",
]
