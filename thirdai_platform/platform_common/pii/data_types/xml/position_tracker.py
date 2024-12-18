import re

from lxml import etree


class PositionTrackingTarget:
    def __init__(self, xml_string):
        self.positions = []
        self.xml_string = xml_string
        self.element_stack_elements = []

        # total offset is the offset in the parsed string whereas pos is the offset in the raw input.
        # example : &amp; is 1 character in parsed string ie '&' but 5 characters in raw input.
        # current implementation has no support for these escaped characters but we might have to in the future.
        self.total_offset = 0
        self.pos = 0

        # maintains a count of the number of times a tag has been seen at each level.
        # useful to get absolute xpaths for duplicate tags.
        self.tag_counter_stack = []

    def _update_position(self, length):
        self.total_offset += length
        self.pos += length

    def start(self, tag, attrib):
        # record the start position
        start_offset = self.total_offset

        # ignore namespaces, use local name
        _, local_name = self._split_namespace(tag)
        tag_name = local_name

        # find the exact start tag in the xml_string
        tag_end_match = re.search(r">", self.xml_string[self.pos :])
        if not tag_end_match:
            raise ValueError("Cannot find end of start tag")
        tag_end_pos = self.pos + tag_end_match.end()
        tag_text = self.xml_string[self.pos : tag_end_pos]

        # determine if the tag is self-closing. self-closing tags have no matching end tag.
        is_self_closing = tag_text.strip().endswith("/>")

        # update the total offset and pos.
        self._update_position(len(tag_text))

        # update the tag counter for the current element.
        if not self.tag_counter_stack:
            # We are at root level
            self.tag_counter_stack.append({})
        current_tag_counts = self.tag_counter_stack[-1]

        # count for xml tags starts from 1.
        # duplicate tags have different counts. ex /a/b[1] and /a/b[2] are different tags.
        count = current_tag_counts.get(tag_name, 0) + 1
        current_tag_counts[tag_name] = count

        # build the xpath for the current element.
        xpath_parts = []
        for elem in self.element_stack_elements:
            xpath_parts.append(f"{elem['name']}[{elem['count']}]")
        xpath_parts.append(f"{tag_name}[{count}]")
        current_xpath = "/" + "/".join(xpath_parts)

        element_entry = {
            "type": "element",
            "name": tag_name,
            "count": count,
            "attrib": {},
            "start_offset": start_offset,
            "end_offset": None,  # To be updated in 'end' method
            "xpath": current_xpath,  # Store the XPath here
            "is_self_closing": is_self_closing,
            "text_start": None,  # Start position of text content
            "text_end": None,  # End position of text content
        }

        # this map will be used to store the positions of the attributes in the xml.
        attrib_positions = {}

        # Exclude the tag name at the beginning
        tag_name_pattern = r"<\s*" + re.escape(tag_name)
        tag_name_match = re.match(tag_name_pattern, tag_text)
        if tag_name_match:
            attr_text = tag_text[tag_name_match.end() : -1]  # Exclude '>' at the end
            if is_self_closing:
                attr_text = attr_text.rstrip("/")  # Exclude '/' for self-closing tags
            attr_offset = start_offset + tag_name_match.end()
        else:
            attr_text = tag_text[1:-1]  # Exclude '<' and '>' at the ends
            attr_offset = start_offset + 1

        # find key value pairs in the element string.
        attr_pattern = re.compile(r'\s+(\S+?)\s*=\s*(["\'])(.*?)\2', re.DOTALL)
        for match in attr_pattern.finditer(attr_text):
            full_attr_name = match.group(1)
            attr_value = match.group(3)
            # Positions in attr_text for the attribute value
            value_start_in_attr_text = match.start(3)
            value_end_in_attr_text = match.end(3)
            value_start = attr_offset + value_start_in_attr_text
            value_end = attr_offset + value_end_in_attr_text

            # ignore namespace, use local name
            _, attr_name = self._split_namespace(full_attr_name)

            attrib_positions[attr_name] = {
                "start": value_start,
                "end": value_end,
                "value": attr_value,
            }

        # text content of an element is mapped to attribute None.
        # data method updates this mapping
        attrib_positions[None] = None

        element_entry["attrib"] = attrib_positions

        # add a new position entry for the current element into the list. this entry will be used to retrieve the charspans for the attributes and text content in the post-processing step.
        self.positions.append(element_entry)

        # push the current element entry onto the stack.
        self.element_stack_elements.append(element_entry)

        self.tag_counter_stack.append({})

    def end(self, tag):
        # Pop the dict from tag_counter_stack
        self.tag_counter_stack.pop()

        # Pop the element entry from the stack
        element_entry = self.element_stack_elements.pop()
        is_self_closing = element_entry["is_self_closing"]

        # Use local name for tag, ignoring namespaces.
        _, local_name = self._split_namespace(tag)
        tag_name = local_name

        if not is_self_closing:
            # Find the exact end tag in the xml_string
            end_tag_pattern = r"</\s*" + re.escape(tag_name) + r"\s*>"
            pattern = re.compile(end_tag_pattern, re.DOTALL)
            match = pattern.search(self.xml_string, self.pos)
            if match:
                tag_text = match.group(0)
                length = match.end() - self.pos
                self._update_position(length)
            else:
                # Fallback: find the next '>' character
                gt_pos = self.xml_string.find(">", self.pos)
                if gt_pos == -1:
                    raise ValueError("Cannot find end of end tag")
                tag_text = self.xml_string[self.pos : gt_pos + 1]
                self._update_position(len(tag_text))
        else:
            # do not need to set end_offset for self-closing tags, already set in start method
            pass

        # Set the end_offset
        element_entry["end_offset"] = self.total_offset

        # If text positions are recorded, map it to attribute None.
        if "text_value" in element_entry:
            element_entry["attrib"][None] = {
                "start": element_entry["text_start"],
                "end": element_entry["text_end"],
                "value": element_entry["text_value"],
            }

    def data(self, data):
        data_length = len(data)

        if data.strip():
            start_offset = self.total_offset
            self._update_position(data_length)
            end_offset = self.total_offset

            # Get the current element to add the text node
            if self.element_stack_elements:
                # only the first text node within an element is added.
                # other text nodes are generally tail nodes for child elements.
                # we are ignoring tail nodes for child elements as of now.
                current_element = self.element_stack_elements[-1]
                if current_element["text_start"] is None:
                    # First text node within this element (the .text)
                    current_element["text_start"] = start_offset
                    current_element["text_end"] = end_offset
                    current_element["text_value"] = data
            else:
                # We are not handling text outside that is not within an element.
                pass
        else:
            self._update_position(data_length)

    def comment(self, text):
        comment_text = f"<!--{text}-->"
        start_offset = self.total_offset
        self._update_position(len(comment_text))
        end_offset = self.total_offset

        # Compute current XPath from the element stack
        current_xpath = self._compute_current_xpath()
        self.positions.append(
            {
                "type": "comment",
                "content": text,
                "start_offset": start_offset,
                "end_offset": end_offset,
                "xpath": current_xpath,
            }
        )

    def close(self):
        char_spans = {}
        # only storing the charspans for elements. assuming comments do not contain pii.
        for position in self.positions:
            # inserting charspans for attributes of elements into the charspans dict.
            if position["type"] == "element":
                for attr, details in position["attrib"].items():
                    if details is not None:
                        char_spans[(position["xpath"], attr)] = details

        for (xpath, attr), details in char_spans.items():
            value_in_xml = self.xml_string[details["start"] : details["end"]]
            assert (
                value_in_xml == details["value"]
            ), f"Parsed value for xpath='{xpath}', attr='{attr}' does not match the value found using character spans in the XML."
        return char_spans

    def _split_namespace(self, tag):
        if "}" in tag:
            namespace_uri, local_name = tag[1:].split("}")
            return namespace_uri, local_name
        else:
            return None, tag

    def _compute_current_xpath(self):
        xpath_parts = []
        for elem in self.element_stack_elements:
            xpath_parts.append(f"{elem['name']}[{elem['count']}]")
        current_xpath = "/" + "/".join(xpath_parts)
        return current_xpath


def parse_xml_with_positions(xml_string):
    parser = etree.XMLParser(
        target=PositionTrackingTarget(xml_string),
        remove_blank_text=False,  # Keep blank text nodes
    )
    try:
        etree.fromstring(xml_string.encode("utf-8"), parser)
    except etree.XMLSyntaxError as e:
        print(f"XML Syntax Error: {e}")
    return parser.target.close()
