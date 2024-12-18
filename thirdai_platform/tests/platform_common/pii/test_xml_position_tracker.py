import pytest
from platform_common.pii.data_types.xml.position_tracker import parse_xml_with_positions

pytestmark = [pytest.mark.unit]


def test_xml_text_extraction():
    xml_string = "<root><parent><child>Content</child></parent></root>"
    char_spans = parse_xml_with_positions(xml_string)

    expected = {
        ("/root[1]/parent[1]/child[1]", None): {
            "value": "Content",
            "start": 21,
            "end": 28,
        },
    }
    assert char_spans == expected


def test_xml_attribute_extraction():
    xml_string = "<root><element attr1='value1' attr2='value2'></element></root>"
    char_spans = parse_xml_with_positions(xml_string)

    expected = {
        ("/root[1]/element[1]", "attr1"): {"value": "value1", "start": 22, "end": 28},
        ("/root[1]/element[1]", "attr2"): {"value": "value2", "start": 37, "end": 43},
    }
    assert char_spans == expected


def test_xml_self_closing_tags():
    xml_string = "<root><empty-element attr='value'/></root>"
    char_spans = parse_xml_with_positions(xml_string)

    expected = {
        ("/root[1]/empty-element[1]", "attr"): {
            "value": "value",
            "start": 27,
            "end": 32,
        },
    }
    assert char_spans == expected


def test_xml_comments_handling():
    xml_string = "<root><!-- This is a comment --><child>Text</child></root>"
    char_spans = parse_xml_with_positions(xml_string)

    expected_positions = {
        ("/root[1]/child[1]", None): {"start": 39, "end": 43, "value": "Text"}
    }
    assert char_spans == expected_positions


def test_xml_text_content_extraction():
    # we ignore the .tail text for the elements
    xml_string = "<root>Leading text<child>Child text</child>Trailing text</root>"
    char_spans = parse_xml_with_positions(xml_string)

    expected = {
        ("/root[1]", None): {"start": 6, "end": 18, "value": "Leading text"},
        ("/root[1]/child[1]", None): {"start": 25, "end": 35, "value": "Child text"},
    }
    assert char_spans == expected


def test_xml_whitespace_handling():
    xml_string = (
        "<root>\n    <child>\n        Text with whitespace\n    </child>\n</root>"
    )
    char_spans = parse_xml_with_positions(xml_string)

    expected = {
        ("/root[1]/child[1]", None): {
            "value": "\n        Text with whitespace\n    ",
            "start": 18,
            "end": 52,
        },
    }
    assert char_spans == expected


def test_xml_namespaces_ignored():
    xml_string = (
        "<ns:root xmlns:ns='http://example.com/ns'><ns:child>Text</ns:child></ns:root>"
    )
    char_spans = parse_xml_with_positions(xml_string)

    expected = {
        ("/root[1]", "xmlns:ns"): {
            "start": 19,
            "end": 40,
            "value": "http://example.com/ns",
        },
        ("/root[1]/child[1]", None): {"start": 52, "end": 56, "value": "Text"},
    }
    assert char_spans == expected


def test_xml_duplicate_tags():
    xml_string = "<root><item>First</item><item>Second</item></root>"
    char_spans = parse_xml_with_positions(xml_string)

    expected = {
        ("/root[1]/item[1]", None): {"value": "First", "start": 12, "end": 17},
        ("/root[1]/item[2]", None): {"value": "Second", "start": 30, "end": 36},
    }
    assert char_spans == expected


def test_xml_complex_xml():
    xml_string = """
    <Event>
        <System>
            <Data name="first_name">John</Data>
            <Data name="last_name">Doe</Data>
        </System>
        <Message>
            Hello, this is a test message.
        </Message>
        <!-- Comment -->
        <EmptyElement attr="value"/>
    </Event>
    """
    char_spans = parse_xml_with_positions(xml_string)

    expected = {
        ("/Event[1]/System[1]/Data[1]", "name"): {
            "value": "first_name",
            "start": 54,
            "end": 64,
        },
        ("/Event[1]/System[1]/Data[1]", None): {
            "value": "John",
            "start": 66,
            "end": 70,
        },
        ("/Event[1]/System[1]/Data[2]", "name"): {
            "value": "last_name",
            "start": 102,
            "end": 111,
        },
        ("/Event[1]/System[1]/Data[2]", None): {
            "value": "Doe",
            "start": 113,
            "end": 116,
        },
        ("/Event[1]/Message[1]", None): {
            "value": "\n            Hello, this is a test message.\n        ",
            "start": 159,
            "end": 211,
        },
        ("/Event[1]/EmptyElement[1]", "attr"): {
            "value": "value",
            "start": 275,
            "end": 280,
        },
    }
    assert char_spans == expected
