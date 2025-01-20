from typing import List, Tuple

from platform_common.pii.data_types.pydantic_models import CharSpan, XMLUserFeedback
from platform_common.pii.data_types.xml.parser import XMLParser
from platform_common.pii.data_types.xml.utils import remove_special_characters
from platform_common.thirdai_storage.data_types import (
    XMLElementData,
    XMLFeedbackData,
    XMLLogData,
)


def convert_charspan_to_token_span(charspan: CharSpan, string: str) -> Tuple[int, int]:
    cleaned_string = remove_special_characters(string)

    # Get start token index
    start_token = len(cleaned_string[: charspan.start].split())
    # Adjust if we're in the middle of a token
    if start_token > 0 and not cleaned_string[charspan.start - 1].isspace():
        start_token -= 1

    # Get end token index
    end_token = len(cleaned_string[: charspan.end].split())
    if (
        charspan.end < len(cleaned_string)
        and not cleaned_string[charspan.end - 1].isspace()
    ):
        end_token -= 1

    return (start_token, end_token)


def convert_xml_feedback_to_storage_format(
    user_feedback: XMLUserFeedback,
) -> Tuple[XMLLogData, List[XMLFeedbackData]]:
    xml_string = user_feedback.xml_string
    feedbacks = user_feedback.feedbacks

    parsed_xml = XMLParser(xml_string, remove_delimiters=False)
    elements = parsed_xml.find_all_elements()

    feedback_data = []
    for feedback in feedbacks:
        xpath = feedback.location.xpath
        attribute = feedback.location.attribute

        xml_reference = parsed_xml.tree.xpath(xpath)
        assert (
            len(xml_reference) == 1
        ), f"Expected 1 XML element by xpath {xpath}, got {len(xml_reference)}"
        xml_reference = xml_reference[0]

        if attribute:
            search_string = xml_reference.attrib[attribute]
        else:
            search_string = xml_reference.text

        token_span = convert_charspan_to_token_span(feedback.charspan, search_string)

        # Create element data
        element_data = XMLElementData(
            xpath=xpath, attribute=attribute, n_tokens=len(search_string.split())
        )

        feedback_data.append(
            XMLFeedbackData(
                element=element_data,
                token_start=token_span[0],
                token_end=token_span[1],
                label=feedback.label,
                user_provided=True,
            )
        )

    log = XMLLogData(xml_string=xml_string, elements=elements)
    return log, feedback_data
