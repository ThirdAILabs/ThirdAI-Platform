from uuid import uuid4

import pytest
from backend.thirdai_storage.data_types import (
    DataSample,
    LabelEntity,
    LabelStatus,
    Metadata,
    MetadataStatus,
    SampleStatus,
    TagMetadata,
    TokenClassificationData,
)
from backend.thirdai_storage.storage import DataStorage, SQLiteConnector


@pytest.fixture
def sqlite_connector():
    return SQLiteConnector(db_path=":memory:")


@pytest.fixture
def data_storage(sqlite_connector):
    return DataStorage(connector=sqlite_connector)


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
    data_storage._per_name_buffer_size = 5  # override buffer limit for testing
    samples = [sample_data() for _ in range(10)]  # Create 10 identical samples
    data_storage.insert_samples(samples)

    assert data_storage._sample_counter["ner"] == 5, "Buffer limit exceeded"


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
