from client.knowledge_extraction import KnowledgeExtraction
from utils import doc_dir
import os
import uuid
import requests
import pytest
import time


def await_report(report_id, client: KnowledgeExtraction):
    for _ in range(200):
        report = client.get_report(report_id)
        status = report["status"]
        if status == "queued" or status == "in_progress":
            time.sleep(1)
        elif status == "failed":
            raise ValueError("report failed")
        else:
            return report["content"]


def test_knowledge_extraction():
    doc = os.path.join(doc_dir(), "apple-10k.pdf")

    client = KnowledgeExtraction(
        "http://localhost:80", email="admin@mail.com", password="password"
    )

    client.create(
        f"knowledge-extraction-{uuid.uuid4()}",
        questions=[
            "net revenue of apple",
            "iphone sales in 2021",
            "a question that should be deleted",
            "did sales in europe change from 2022 to 2023",
            "how much did apple spend on research and development in 2021",
        ],
    )

    client.start()
    client.wait_for_deployment(100)

    client.add_question("what were the EPS in 2022")
    questions = client.list_questions()
    qid = [q["question_id"] for q in questions if "EPS" in q["question_text"]]
    client.add_keywords(qid[0], ["earnings", "per", "share"])
    qid = [q["question_id"] for q in questions if "deleted" in q["question_text"]]
    client.delete_question(qid[0])

    report = client.create_report([doc])

    report = await_report(report, client)

    question_to_expected_answer = {
        "net revenue of apple": "383.3",
        "iphone sales in 2021": "191,973",
        "did sales in europe change from 2022 to 2023": "decreased",
        "how much did apple spend on research and development in 2021": "21,914",
        "what were the EPS in 2022": "6.15",
    }

    question_to_answer = {res["question"]: res["answer"] for res in report["results"]}

    assert len(question_to_answer) == len(question_to_expected_answer)
    for question, expected_answer in question_to_expected_answer.items():
        assert question in question_to_answer
        assert expected_answer in question_to_answer[question]

    client.delete_report(report["report_id"])

    with pytest.raises(requests.exceptions.HTTPError, match=".*404.*"):
        client.get_report(report["report_id"])

    client.stop()
