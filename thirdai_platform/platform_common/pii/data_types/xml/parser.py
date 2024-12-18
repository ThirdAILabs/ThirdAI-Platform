from __future__ import annotations

import typing
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from lxml import etree
from platform_common.pii.data_types.xml.utils import (
    remove_delimiters_from_xml,
    remove_namespaces,
)
from pydantic import BaseModel


class XMLTokenInfo(BaseModel):
    xpath: str  # to locate the xml tag which contains the token to be tagged. note that if there are multiple child tags with the same name, then they will contain an index as well ex : a/b[2] that is 2nd tag b under a is the relevant one
    attribute: Optional[
        str
    ]  # if attribute is None implies wrapped fully withing the tag

    ntokens: int
    index_to_label_dict: typing.Dict[int, str] = None

    def update(self, new_info: XMLTokenInfo):
        assert new_info.xpath == self.xpath
        assert new_info.attribute == self.attribute

        if self.index_to_label_dict is None:
            self.index_to_label_dict = new_info.index_to_label_dict

        else:
            for key, value in new_info.index_to_label_dict.items():
                if key not in self.index_to_label_dict:
                    self.index_to_label_dict[key] = value


class XMLParser:
    def __init__(self, xml_string: str, remove_delimiters: bool = False):
        self.xml_string = xml_string
        self.root = etree.fromstring(bytes(xml_string, encoding="utf-8"))
        self.tree = etree.ElementTree(self.root)

        remove_namespaces(self.root)

        if remove_delimiters:
            remove_delimiters_from_xml(self.root)

        # this is a dictionary of xpath for fast lookups to see what paths are actually relevant
        self.token_info = defaultdict(dict)

        # this parameter is used to specify how many ancestor tag str to add to the current tag. this is for providing extra context information for the tag.
        self.parent_key_level = 2

    def normalize_xpath(self, xpath: str) -> str:
        elements = self.tree.xpath(xpath)

        if not elements:
            raise ValueError(f"XPath {xpath} did not match any elements")

        if len(elements) > 1:
            raise ValueError(f"XPath {xpath} matched multiple elements")

        return self.tree.getpath(elements[0])

    def tag(self, token: XMLTokenInfo):
        """
        This function is used to assign a label to a token inside a tag in the XML.
        Parameters:
            token: XMLTokenInfo
                This is the token info object which contains the xpath, attribute, index_to_label_dict, ntokens.

        Notes:
            The xpath is normalized to get the actual tag in the XML.
        """
        normalized_xpath = self.normalize_xpath(token.xpath)
        normalized_token = XMLTokenInfo(
            xpath=normalized_xpath,
            attribute=token.attribute,
            index_to_label_dict=token.index_to_label_dict,
            ntokens=token.ntokens,
        )

        if normalized_xpath in self.token_info:
            if token.attribute in self.token_info[normalized_xpath]:
                self.token_info[normalized_xpath][token.attribute].update(
                    normalized_token
                )
                return

        self.token_info[normalized_xpath][token.attribute] = normalized_token

    def _get_token_info(self, xpath: str, attribute: str) -> XMLTokenInfo:
        if xpath not in self.token_info:
            return None

        if attribute not in self.token_info[xpath]:
            return None

        return self.token_info[xpath][attribute]

    def _tag_single_string(
        string, token_info: Optional[XMLTokenInfo] = None, for_inference: bool = False
    ):

        if token_info is None:
            tokens = string.split()
            tags = ["O"] * len(tokens)
            return tokens, tags

        tokens = string.split()
        tags = ["O"] * len(tokens)

        for index, label in token_info.index_to_label_dict.items():
            tags[index] = label

        return tokens, tags if not for_inference else ["O"] * len(tags)

    def sample(self, for_inference: bool = False) -> List[Tuple[str, str]]:
        tokens = []
        tags = []
        xpath_to_token_index: Dict[Tuple[str, Optional[str]], Tuple[int, int]] = {}

        def process_element(element: etree.Element):
            nonlocal tokens, tags, xpath_to_token_index

            position_path = self.tree.getpath(element)
            current_tags = position_path.split("/")

            # Add opening tag
            context_keys = [
                f"<{key.split('[')[0]}>"
                for key in current_tags[-self.parent_key_level :]
            ]
            context_tokens = ["O"] * len(context_keys)

            # Process attributes and then process the rawString encapsulated inside the tag
            entities_to_sample = element.attrib.items()

            if element.text is not None and len(element.text.strip()) > 0:
                entities_to_sample.append((None, element.text))

            for attr, value in entities_to_sample:
                if value is None:
                    continue

                # each attribute has context keys
                tokens += context_keys
                tags += context_tokens

                tokens += attr.split() if attr is not None else []
                tags += ["O"] * len(attr.split()) if attr is not None else []

                attribute_tokens, attribute_tags = XMLParser._tag_single_string(
                    string=value,
                    token_info=self._get_token_info(
                        xpath=position_path, attribute=attr
                    ),
                    for_inference=for_inference,
                )

                xpath_to_token_index[(position_path, attr)] = (
                    len(tokens),
                    len(tokens) + len(attribute_tokens),
                )

                tokens += attribute_tokens
                tags += attribute_tags

            # Process children
            for child in element:
                process_element(child)

        process_element(self.root)
        return tokens, tags, xpath_to_token_index
