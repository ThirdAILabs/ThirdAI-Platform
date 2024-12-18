import re
from string import punctuation

from lxml import etree

exception_characters = set([" "]).union(set(punctuation))


def replace_whitespace_with_space(text: str) -> str:
    # Replace all whitespace characters with a single space
    return re.sub(r"\s+", " ", text).strip()


def remove_special_characters(text: str) -> str:
    text = re.sub(r'[:\|"<>\',=%{}&]', " ", text)
    return text


def clean(log: str) -> str:
    # Ensure non-printable characters are removed
    clean_string = re.sub(r"[^\x20-\x7E\t\n\r]", "", log)
    clean_string = re.sub(r"\\\\", r"\\", clean_string)
    return clean_string


def clean_and_extract_xml_block(rawlog):
    def extract_xml_block(text):
        pattern = r"<(\w+)(?:\s[^>]*)?>.*?</\1>"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(0)  # Return the full XML block
        else:
            return None

    return clean(extract_xml_block(rawlog))


def remove_namespaces(tree):
    """Recursively remove namespaces from an lxml etree."""
    for elem in tree.getiterator():
        # Splits the tag string on '}' and returns the second part, if present, otherwise the whole string
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]
        # Remove namespace attributes
        for key in list(elem.attrib):
            if "}" in key:
                new_key = key.split("}", 1)[1]
                elem.attrib[new_key] = elem.attrib[key]
                del elem.attrib[key]


def remove_delimiters_from_xml(tree):
    for elem in tree.iter():
        if elem.text is not None:
            elem.text = replace_whitespace_with_space(
                remove_special_characters(elem.text)
            )

        for attr, value in elem.attrib.items():
            elem.attrib[attr] = replace_whitespace_with_space(
                remove_special_characters(value)
            )


def convert_xpath_using_attributes(xml_root: etree.Element, xpath: str) -> str:
    # Find the element(s) using the original XPath
    elements = xml_root.xpath(xpath)

    if not elements:
        # If the element is not found, return the XPath with the last index removed
        raise ValueError(f"XPath {xpath} did not match any elements")

    # Assume we are working with the first matched element
    element = elements[0]

    # Build the attribute-based XPath by traversing up the tree
    path_parts = []
    current_element = element
    while current_element is not None:
        # Get parent element
        parent = current_element.getparent()
        if parent is None:
            # Reached the root element
            path_parts.insert(0, current_element.tag)
            break
        else:
            # Get all siblings with the same tag under the same parent
            siblings = parent.findall(current_element.tag)
            # Try to find a unique attribute to identify the element among its siblings
            unique_attr = None
            for attr_name, attr_value in current_element.attrib.items():
                # Check if this attribute uniquely identifies the element among its siblings
                matching_siblings = [
                    s for s in siblings if s.attrib.get(attr_name) == attr_value
                ]
                if len(matching_siblings) == 1:
                    unique_attr = (attr_name, attr_value)
                    break
            if unique_attr:
                # Use the unique attribute to identify the element
                attr_name, attr_value = unique_attr
                path_part = f"{current_element.tag}[@{attr_name}='{attr_value}']"
            else:
                # Use position index if no unique attribute is found
                index = siblings.index(current_element) + 1  # XPath indices are 1-based
                path_part = f"{current_element.tag}[{index}]"
            path_parts.insert(0, path_part)
            current_element = parent

    # Build the full attribute-based XPath
    attribute_based_xpath = "/" + "/".join(path_parts)
    return attribute_based_xpath


def find_span(s1, s2):
    escaped_s2 = re.escape(s2)
    pattern = escaped_s2.replace(r"\ ", r"[\s\W]+")
    pattern = pattern.replace(r"\.", r"\.?")

    regex = re.compile(pattern)

    match = regex.search(s1)
    if match:
        start_pos = match.start()
        end_pos = match.end()
        matched_substring = s1[start_pos:end_pos]

        # clean both the strings and compare
        c_clean = re.sub(r"[\s\W]+", "", matched_substring)
        s2_clean = re.sub(r"[\s\W]+", "", s2)

        if c_clean == s2_clean:
            return start_pos, end_pos, matched_substring
    return None
