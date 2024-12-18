import shutil
from pathlib import Path

import pytest
from deployment_job.guardrail import Guardrail, LabelMap
from platform_common.logging import JobLogger


@pytest.fixture(scope="function")
def test_logger():
    log_dir = Path("./tmp")
    if log_dir.exists():
        shutil.rmtree(log_dir)

    logger = JobLogger(
        log_dir=log_dir,
        log_prefix="deployment",
        service_type="deployment",
        model_id="model-123",
        model_type="ndb",
        user_id="user-123",
    )
    yield logger
    if log_dir.exists():
        shutil.rmtree(log_dir)


def fake_ner_output(text, access_token):
    tokens = [
        ("my", "O"),
        ("neighbor", "O"),
        ("is", "O"),
        ("rick", "NAME"),
        ("on", "O"),
        ("main", "ADDRESS"),
        ("street", "ADDRESS"),
        ("he", "O"),
        ("has", "O"),
        ("a", "O"),
        ("cat", "O"),
        ("named", "O"),
        ("robert", "NAME"),
        ("we", "O"),
        ("call", "O"),
        ("him", "O"),
        ("cat", "NAME"),
        ("robert", "NAME"),
    ]

    tokens, tags = list(zip(*tokens))

    return {"tokens": tokens, "predicted_tags": [[tag] for tag in tags]}


def test_guardrail(test_logger):
    guardrail = Guardrail("", "", test_logger)

    # override the query_pii_model method
    guardrail.query_pii_model = fake_ner_output

    label_map = LabelMap()

    expected_redacted_pii = "my neighbor is [NAME#0] on [ADDRESS#1] he has a cat named [NAME#2] we call him [NAME#2]"

    redacted = guardrail.redact_pii("", "", label_map)
    assert redacted == expected_redacted_pii

    # Check that labels are reused between calls
    assert guardrail.redact_pii("", "", label_map) == expected_redacted_pii

    expected_unredacted_pii = "my neighbor is rick on main street he has a cat named robert we call him robert"

    unredacted = guardrail.unredact_pii(redacted, label_map.get_entities())

    assert unredacted == expected_unredacted_pii

    assert (
        guardrail.unredact_pii("[NAME#4]", label_map.get_entities())
        == "[UNKNOWN ENTITY]"
    )
