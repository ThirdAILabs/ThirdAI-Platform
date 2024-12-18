from collections import defaultdict
from typing import List, Tuple

from platform_common.pii.data_types.base import DataType
from platform_common.pii.data_types.pydantic_models import (
    CharSpan,
    XMLLocation,
    XMLPrediction,
    XMLTokenClassificationResults,
    XPathLocation,
)
from platform_common.pii.data_types.xml.parser import XMLParser
from platform_common.pii.data_types.xml.position_tracker import parse_xml_with_positions
from platform_common.pii.data_types.xml.utils import (
    clean_and_extract_xml_block,
    convert_xpath_using_attributes,
    find_span,
)


class XMLLog(DataType):
    def __init__(self, log: str):
        # extract the xml block
        self.clean_log = clean_and_extract_xml_block(log)

        self.clean_xml = XMLParser(xml_string=self.clean_log, remove_delimiters=True)

        self.original_xml = XMLParser(xml_string=log, remove_delimiters=False)

        source, _, xpath_to_token = self.clean_xml.sample(for_inference=True)
        self._inference_sample = {"source": " ".join(source)}

        # this is a mapping from xpath and attribute to the token indices of the inference sample
        self.xpath_to_token = xpath_to_token

        # reverse mapping from token index to xpath and attribute
        self.index_to_xpath_attr = {}
        for (xpath, attr), (start_idx, end_idx) in self.xpath_to_token.items():
            for index in range(start_idx, end_idx):
                self.index_to_xpath_attr[index] = (xpath, attr)

        positions = parse_xml_with_positions(self.clean_log)
        self.char_spans = {}
        for (xpath, attr), details in positions.items():
            normalized_xpath = self.clean_xml.normalize_xpath(xpath)
            self.char_spans[(normalized_xpath, attr)] = details

    @property
    def inference_sample(self):
        return self._inference_sample

    def process_prediction(self, model_predictions: List[List[Tuple[str, float]]]):
        tokens = self._inference_sample["source"].split()

        labels = defaultdict(list)

        for index in range(len(model_predictions)):
            top_prediction = model_predictions[index][0]
            tag = top_prediction[0]

            if tag != "O":
                labels[tag].append(index)

        predictions: List[XMLPrediction] = []
        for label, positions in labels.items():
            processed_positions = self.process_labels(tokens, positions)
            for processed_position in processed_positions:
                predictions.append(
                    XMLPrediction(
                        label=label,
                        location=processed_position,
                    )
                )

        # convert xpath from location to attribute based
        for prediction in predictions:
            prediction.location.xpath_location.xpath = convert_xpath_using_attributes(
                xml_root=self.original_xml.root,
                xpath=prediction.location.xpath_location.xpath,
            )

        return XMLTokenClassificationResults(
            data_type="xml",
            query_text=self.clean_log,
            predictions=predictions,
        )

    def find_charspan_in_xml(self, xpath, attr, search_string):
        if (xpath, attr) in self.char_spans:
            details = self.char_spans[(xpath, attr)]
            value = details["value"]

            try:
                start_pos, end_pos, c = find_span(value, search_string)
            except:
                print(
                    f"Error finding span for search_string {search_string} in {xpath} and {attr} in {value}"
                )
                return None, None, None

            assert end_pos <= details["end"] - details["start"]

            global_char_span = CharSpan(
                start=details["start"] + start_pos,
                end=details["start"] + end_pos,
            )

            local_char_span = CharSpan(
                start=start_pos,
                end=end_pos,
            )
            return global_char_span, local_char_span, c

        else:
            raise ValueError(f"No charspan found for {xpath} and {attr}")

    def process_labels(self, tokens, positions: List[int]) -> List[Tuple[str, str]]:
        # given xpath to token, we need to first segment the list into different parts where each part is contained wholly within a single xpath attribute.
        # if two non-contiguous parts are from the same xpath attribute, we merge the entire span into a single value.

        intervals = defaultdict(list)

        for position in positions:
            if position in self.index_to_xpath_attr:
                xpath, attr = self.index_to_xpath_attr[position]
                intervals[(xpath, attr)].append(position)

        # merging phase
        result = []
        for (xpath, attr), indices in intervals.items():
            min_index = min(indices)
            max_index = max(indices)

            merged_tokens = " ".join(tokens[min_index : max_index + 1])

            xpath_location = XPathLocation(xpath=xpath, attribute=attr)
            global_char_span, local_char_span, value_in_xml = self.find_charspan_in_xml(
                xpath, attr, merged_tokens
            )

            location = XMLLocation(
                global_char_span=global_char_span,
                local_char_span=local_char_span,
                xpath_location=xpath_location,
                value=value_in_xml,
            )

            result.append(location)

        return result
