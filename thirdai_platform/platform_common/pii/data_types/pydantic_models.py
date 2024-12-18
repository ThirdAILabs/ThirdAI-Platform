from typing import List, Literal, Optional

from pydantic import BaseModel

"""
    global_char_span: Character span relative to start of entire XML log (position 0)
    local_char_span: Character span relative to start of the tag's content
    xpath_location: XPath expression to locate the element and optional attribute
    value: The actual text value found at this location

    For an XML log like:
    <a type="name"> stark </a>

    The spans and locations would be:
    - global_char_span: CharSpan(start=15, end=20) - Position relative to start of entire log
    - local_char_span: CharSpan(start=1, end=6) - Position relative to start of tag content
    - xpath_location: XPathLocation(xpath="/a[@type='name']", attribute=None)
    - value: "stark"

    Refer to : https://www.w3schools.com/xml/xpath_syntax.asp
"""


class XPathLocation(BaseModel):
    """
    If attribute is None, then the location is the text of the tag. Else, it is the text of the attribute.
    """

    xpath: str
    attribute: Optional[str]


class CharSpan(BaseModel):
    start: int
    end: int


class XMLLocation(BaseModel):
    global_char_span: CharSpan
    local_char_span: CharSpan
    xpath_location: XPathLocation
    value: str


class XMLPrediction(BaseModel):
    label: str
    location: XMLLocation


class XMLTokenClassificationResults(BaseModel):
    data_type: Literal["xml"]
    query_text: str
    predictions: List[XMLPrediction]


class UnstructuredTokenClassificationResults(BaseModel):
    data_type: Literal["unstructured"]
    query_text: str
    tokens: List[str]
    predicted_tags: List[List[str]]
