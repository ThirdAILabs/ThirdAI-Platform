from platform_common.pii.data_types.pydantic_models import (
    UnstructuredTokenClassificationResults,
    XMLTokenClassificationResults,
    XMLUserFeedback,
)
from platform_common.pii.data_types.unstructured import UnstructuredText
from platform_common.pii.data_types.xml import XMLLog
from platform_common.pii.data_types.xml.storage_converter import (
    convert_xml_feedback_to_storage_format,
)


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
    "XMLUserFeedback",
    "convert_xml_feedback_to_storage_format",
]
