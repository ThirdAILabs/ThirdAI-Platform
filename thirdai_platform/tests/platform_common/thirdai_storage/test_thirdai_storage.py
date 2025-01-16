from uuid import uuid4

import pytest
from platform_common.pii.data_types import (
    XMLUserFeedback,
    convert_xml_feedback_to_storage_format,
)
from platform_common.thirdai_storage.data_types import (
    DataSample,
    LabelEntity,
    LabelStatus,
    Metadata,
    MetadataStatus,
    SampleStatus,
    TagMetadata,
    TokenClassificationData,
    XMLElementData,
    XMLFeedbackData,
)
from platform_common.thirdai_storage.schemas import XMLElement, XMLLog
from platform_common.thirdai_storage.storage import DataStorage

pytestmark = [pytest.mark.unit]


@pytest.fixture
def data_storage():
    return DataStorage(db_path=":memory:")


def sample_data():
    return DataSample(
        name="ner",
        data=TokenClassificationData(tokens=["Name", "Shubh"], tags=["O", "NAME"]),
        user_provided=True,
        status=SampleStatus.untrained,
        unique_id=str(uuid4()),
    )


@pytest.fixture
def tag_metadata():
    return TagMetadata(
        tag_status={
            "B-LOC": LabelEntity(name="NAME", status=LabelStatus.untrained),
            "O": LabelEntity(name="O", status=LabelStatus.untrained),
        }
    )


def test_insert_samples_buffer_limit(data_storage):
    data_storage._reservoir_size = 5  # override buffer limit for testing
    samples = [sample_data() for _ in range(10)]  # Create 10 identical samples
    data_storage.insert_samples(samples)

    samples = data_storage.retrieve_samples("ner", num_samples=5, user_provided=True)

    assert len(samples) == 5, "Reservoir Size limit exceeded"


def test_rollback_metadata(data_storage, tag_metadata):
    original_metadata = Metadata(name="tags_and_status", data=tag_metadata)
    data_storage.insert_metadata(original_metadata)

    # make copy and update
    metadata = original_metadata.model_copy(deep=True)
    metadata.data.add_tag(
        LabelEntity(
            name="ADDRESS",
        )
    )
    metadata.status = MetadataStatus.updated
    data_storage.insert_metadata(metadata)

    # Simulate rollback
    data_storage.rollback_metadata(name="tags_and_status")
    updated_metadata = data_storage.get_metadata("tags_and_status")

    assert (
        updated_metadata == original_metadata
    ), "Metadata status should be reset after rollback"


def test_metadata_status_after_training(data_storage, tag_metadata):
    metadata = Metadata(
        name="tags_and_status", data=tag_metadata, status=MetadataStatus.updated
    )
    data_storage.insert_metadata(metadata)

    # Simulate model training completion
    for tag in tag_metadata.tag_status:
        tag_metadata.tag_status[tag].status = LabelStatus.trained

    data_storage.insert_metadata(metadata)
    data_storage.update_metadata_status("tags_and_status", MetadataStatus.unchanged)

    updated_metadata = data_storage.get_metadata("tags_and_status")

    assert (
        updated_metadata.status == MetadataStatus.unchanged
    ), "Metadata status should be unchanged after training"

    for tags in updated_metadata.data.tag_status:
        assert (
            updated_metadata.data.tag_status[tags].status == LabelStatus.trained
        ), "Tag status should be trained after training"


def test_sample_status_after_training(data_storage):
    data_storage.insert_samples([sample_data() for _ in range(10)])

    data_storage.update_sample_status("ner", SampleStatus.trained)

    samples = data_storage.retrieve_samples("ner", num_samples=1, user_provided=True)

    for sample in samples:
        assert (
            sample.status == SampleStatus.trained
        ), "Sample status should be trained after training"


def test_metadata_serialization(tag_metadata):
    metadata = Metadata(
        name="tags_and_status", data=tag_metadata, status=MetadataStatus.updated
    )
    serialized_data = metadata.serialize_data()

    deserialized_metadata = Metadata.from_serialized(
        type="token_classification_tags",
        name="tags_and_status",
        status=MetadataStatus.updated,
        serialized_data=serialized_data,
    )

    assert (
        deserialized_metadata == metadata
    ), "Deserialized metadata does not match the original"


def test_remove_untrained_samples(data_storage):
    # Insert some untrained samples
    untrained_samples = [sample_data() for _ in range(5)]
    data_storage.insert_samples(untrained_samples)

    # Remove untrained samples
    data_storage.remove_untrained_samples("ner")

    remaining_samples = data_storage.retrieve_samples(
        "ner", num_samples=5, user_provided=True
    )
    assert len(remaining_samples) == 0, "Untrained samples should be removed"


def test_xml_basic_insertion(data_storage):
    xml_query = """<Employee>
  <Email Name = "email">
          shubh@thirdai.com
  </Email>
</Employee>"""
    log, feedbacks = convert_xml_feedback_to_storage_format(
        XMLUserFeedback(datatype="xml", xml_string=xml_query, feedbacks=[])
    )

    assert len(log.elements) == 2, "Expected 2 elements in the log"
    assert len(feedbacks) == 0, "Expected 0 feedbacks"
    assert log.elements[0] == XMLElementData(
        xpath="/Employee/Email[@Name='email']", attribute="Name", n_tokens=1
    )
    assert log.elements[1] == XMLElementData(
        xpath="/Employee/Email[@Name='email']", attribute=None, n_tokens=1
    )

    log_id = data_storage.add_xml_log(log)

    inserted_log = data_storage.get_xml_log_by_id(log_id)

    assert inserted_log.xml_string == log.xml_string
    assert len(inserted_log.elements) == 2

    assert inserted_log.elements[0] == log.elements[0]
    assert inserted_log.elements[1] == log.elements[1]


def test_xml_basic_feedback(data_storage):
    xml_query = """<Employee>
  <Email Name = "email">
          shubh@thirdai.com
  </Email>
  <Phone Type = "work">
          123-456-7890
  </Phone>
</Employee>"""

    # Create initial XML log with elements but no feedback
    log, feedbacks = convert_xml_feedback_to_storage_format(
        XMLUserFeedback(datatype="xml", xml_string=xml_query, feedbacks=[])
    )

    assert len(log.elements) == 4  # 2 elements with attributes, 2 without
    log_id = data_storage.add_xml_log(log)

    # Create feedback for email
    feedback_items = [
        XMLFeedbackData(
            element=XMLElementData(
                xpath="/Employee/Email[@Name='email']",
                attribute=None,
                n_tokens=1,
            ),
            token_start=0,
            token_end=1,
            label="EMAIL",
        )
    ]

    data_storage.store_user_xml_feedback(log_id, feedback_items)

    # Verify storage
    session = data_storage.xml.Session()
    inserted_log = session.query(XMLLog).get(log_id)
    assert len(inserted_log.feedback) == 1
    assert inserted_log.feedback[0].element.xpath == "/Employee/Email[@Name='email']"
    assert inserted_log.feedback[0].label == "EMAIL"


def test_xml_element_reuse(data_storage):
    xml1 = """<Employee>
  <Email Name = "email">
          shubh@thirdai.com
  </Email>
</Employee>"""

    xml2 = """<Employee>
  <Email Name = "email">
          david@thirdai.com
  </Email>
  <Phone>
          123-456-7890
  </Phone>
</Employee>"""

    log1, _ = convert_xml_feedback_to_storage_format(
        XMLUserFeedback(datatype="xml", xml_string=xml1, feedbacks=[])
    )
    data_storage.add_xml_log(log1)

    log2, _ = convert_xml_feedback_to_storage_format(
        XMLUserFeedback(datatype="xml", xml_string=xml2, feedbacks=[])
    )
    data_storage.add_xml_log(log2)

    # log1 and log2 have overlapping element /Employee/Email[@Name='email']
    # with attr email and /Employee/Email[@Name='email'] with attr None
    session = data_storage.xml.Session()
    element_count = session.query(XMLElement).count()
    assert element_count == 3


def test_xml_feedback_conflict(data_storage):
    xml_query = """<Employee>
  <Email Name = "email">
          shubh@thirdai.com
  </Email>
</Employee>"""

    log, _ = convert_xml_feedback_to_storage_format(
        XMLUserFeedback(datatype="xml", xml_string=xml_query, feedbacks=[])
    )
    log_id = data_storage.add_xml_log(log)

    feedback_items = [
        XMLFeedbackData(
            element=XMLElementData(
                xpath="/Employee/Email[@Name='email']",
                attribute=None,
                n_tokens=1,
            ),
            token_start=0,
            token_end=4,
            label="EMAIL",
            user_provided=True,
        ),
        XMLFeedbackData(
            element=XMLElementData(
                xpath="/Employee/Email[@Name='email']",
                attribute="Name",
                n_tokens=1,
            ),
            token_start=0,
            token_end=1,
            label="DATA_TYPE",
            user_provided=True,
        ),
    ]
    data_storage.store_user_xml_feedback(log_id, feedback_items)

    conflicting_feedback = XMLFeedbackData(
        element=XMLElementData(
            xpath="/Employee/Email[@Name='email']",
            attribute=None,
            n_tokens=1,
        ),
        token_start=0,
        token_end=1,
        label="NOT_EMAIL",
        user_provided=True,
    )

    conflicts = data_storage.find_conflicting_xml_feedback(conflicting_feedback)
    assert len(conflicts) == 1
    assert conflicts[0].element.xpath == "/Employee/Email[@Name='email']"
    assert conflicts[0].label == "EMAIL"
