import pytest
from platform_common.pii.data_types.xml.impl import XMLLog

pytestmark = [pytest.mark.unit]

xml_string = """
<Event>
  <System>
    <Data name="first_name">
      Shubh
    </Data>
    <Data name="last_name">
      Gupta
    </Data>
  </System>
  <Message>
    I work at {ThirdAI Corp}.
  </Message>
</Event>
"""


def test_xml_logtype_end_to_end():
    log = XMLLog(log=xml_string)

    inference_sample = log.inference_sample

    assert inference_sample == {
        "source": "<System> <Data> name first_name <System> <Data> Shubh <System> <Data> name last_name <System> <Data> Gupta <Event> <Message> I work at ThirdAI Corp ."
    }

    predictions = [[("O", 1.0)] for token in inference_sample["source"].split()]
    predictions[6] = [("FIRST_NAME", 1.0)]
    predictions[13] = [("LAST_NAME", 1.0)]
    predictions[19] = [("COMPANY", 1.0)]
    predictions[20] = [("COMPANY", 1.0)]

    predictions = log.process_prediction(model_predictions=predictions)

    assert predictions.data_type == "xml"
    assert (
        predictions.query_text
        == '<Event>\n  <System>\n    <Data name="first_name">\n      Shubh\n    </Data>\n    <Data name="last_name">\n      Gupta\n    </Data>\n  </System>\n  <Message>\n    I work at {ThirdAI Corp}.\n  </Message>\n</Event>'
    )

    actual_predictions = [
        {
            "label": "FIRST_NAME",
            "location": {
                "global_char_span": {"start": 54, "end": 59},
                "local_char_span": {"start": 7, "end": 12},
                "xpath_location": {
                    "xpath": "/Event/System[1]/Data[@name='first_name']",
                    "attribute": None,
                },
                "value": "Shubh",
            },
        },
        {
            "label": "LAST_NAME",
            "location": {
                "global_char_span": {"start": 106, "end": 111},
                "local_char_span": {"start": 7, "end": 12},
                "xpath_location": {
                    "xpath": "/Event/System[1]/Data[@name='last_name']",
                    "attribute": None,
                },
                "value": "Gupta",
            },
        },
        {
            "label": "COMPANY",
            "location": {
                "global_char_span": {"start": 163, "end": 175},
                "local_char_span": {"start": 16, "end": 28},
                "xpath_location": {"xpath": "/Event/Message[1]", "attribute": None},
                "value": "ThirdAI Corp",
            },
        },
    ]

    assert len(predictions.predictions) == len(actual_predictions)
    for pred, actual_pred in zip(predictions.predictions, actual_predictions):
        assert pred.label == actual_pred["label"]
        assert (
            pred.location.global_char_span.model_dump()
            == actual_pred["location"]["global_char_span"]
        )
        assert (
            pred.location.local_char_span.model_dump()
            == actual_pred["location"]["local_char_span"]
        )
        assert (
            pred.location.xpath_location.model_dump()
            == actual_pred["location"]["xpath_location"]
        )
        assert pred.location.value == actual_pred["location"]["value"]
