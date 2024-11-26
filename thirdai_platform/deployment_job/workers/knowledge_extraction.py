import logging
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
import json

import requests
from platform_common.knowledge_extraction.schema import Keyword, Question, Report
from platform_common.ndb.ndbv2_parser import parse_doc
from platform_common.pydantic_models.deployment import DeploymentConfig
from sqlalchemy import create_engine
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import scoped_session, sessionmaker, selectinload
from thirdai import neural_db_v2 as ndb
from platform_common.pydantic_models.training import FileInfo
from platform_common.logging import setup_logger
from platform_common.file_handler import expand_cloud_buckets_and_directories


def load_config():
    with open(os.getenv("CONFIG_PATH")) as file:
        return DeploymentConfig.model_validate_json(file.read())


class ReportProcessorWorker:
    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.db_path = (
            Path(self.config.model_bazaar_dir)
            / "models"
            / config.model_id
            / "knowledge.db"
        )
        self.reports_base_path = (
            Path(self.config.model_bazaar_dir) / "models" / config.model_id / "reports"
        )
        self.logger = logging.getLogger("ReportProcessorWorker")

        self.engine = create_engine(f"sqlite:///{self.db_path}")
        self.Session = scoped_session(sessionmaker(bind=self.engine))

        self.llm_endpoint = urljoin(
            self.config.model_bazaar_endpoint, "llm-dispatch/generate"
        )

    def fetch_and_lock_pending_report(self):
        with self.Session() as session:
            try:
                report = (
                    session.query(Report)
                    .filter(Report.status == "queued")
                    .order_by(Report.submitted_at.asc())  # Process oldest first
                    .with_for_update(skip_locked=True)  # Lock row to prevent conflicts
                    .first()
                )

                if report:
                    report.status = "in_progress"
                    report.updated_at = datetime.utcnow()
                    session.commit()
                    self.logger.info(f"Locked report for processing: {report.id}")

                return report

            except NoResultFound:
                return None
            except Exception as e:
                self.logger.error(f"Error fetching pending report: {e}")
                return None

    def get_questions(self):
        with self.Session() as session:
            questions = (
                session.query(Question).options(selectinload(Question.keywords)).all()
            )
            if not questions:
                self.logger.info("No questions available for processing.")
                raise ValueError("No questions found in the database.")

        return questions

    def get_keywords(self, question_id):
        with self.Session() as session:
            keywords = (
                session.query(Keyword).filter(Keyword.question_id == question_id).all()
            )

            return [keyword.keyword_text for keyword in keywords]

    def process_report(self, report: Report):
        try:
            self.logger.info(f"Processing report: {report.id}")

            documents_file = self.reports_base_path / str(report.id) / "documents.json"

            if not documents_file.exists():
                self.logger.error(f"Documents file missing for report {report.id}.")
                raise FileNotFoundError(
                    f"Documents file missing for report {report.id}."
                )

            with open(documents_file) as file:
                documents = json.load(file)

            documents = [FileInfo.model_validate(doc) for doc in documents]
            documents = expand_cloud_buckets_and_directories(documents)

            if not documents:
                self.logger.error(f"No documents found for report {report.id}.")
                raise ValueError(f"No documents found for report {report.id}.")

            questions = self.get_questions()

            docs = []
            for doc in documents:
                self.logger.info(f"parsing document: {doc.path}")
                docs.append(
                    parse_doc(
                        doc=doc,
                        doc_save_dir=str(
                            self.reports_base_path / str(report.id) / "documents"
                        ),
                        tmp_dir=str(
                            self.reports_base_path / str(report.id) / "documents/tmp"
                        ),
                    )
                )
                self.logger.info(f"parsed document: {doc.path}")

            total_chunks = 0
            for doc in docs:
                for chunk in doc.chunks():
                    total_chunks += len(chunk.text)

            self.logger.info(f"total chunks: {total_chunks}")

            db = ndb.NeuralDB(splade=(total_chunks < 5000))

            self.logger.info("begining indexing")
            db.insert(docs)
            self.logger.info(
                f"indexing complete, ndocs={len(docs)} chunks={db.retriever.retriever.size()}"
            )

            queries = []
            for question in questions:
                query = question.question_text
                for keyword in question.keywords:
                    query += " " + keyword.keyword_text
                queries.append(query)

            batch_results = db.search_batch(queries, top_k=5, rerank=True)

            report_results = []
            for question, refs in zip(questions, batch_results):
                refs = [
                    {"text": chunk.text, "source": chunk.document} for chunk, _ in refs
                ]
                answer = self.generate(
                    question=question.question_text,
                    references=refs,
                )
                report_results.append(
                    {
                        "question": question.question_text,
                        "answer": answer,
                        "references": refs,
                    }
                )

            report_file_path = self.reports_base_path / str(report.id) / "report.json"
            report_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(report_file_path, mode="w") as writer:
                json.dump({"report_id": report.id, "results": report_results}, writer)

            with self.Session() as session:
                report = session.query(Report).get(report.id)
                report.status = "complete"
                report.updated_at = datetime.utcnow()
                session.commit()
                self.logger.info(
                    f"set report status to complete for report {report.id}"
                )

            self.logger.info(f"Successfully processed report: {report.id}")

        except Exception as e:
            self.logger.error(f"Error processing report {report.id}: {e}")
            with self.Session() as session:
                report = session.query(Report).get(report.id)
                report.status = "failed"
                report.updated_at = datetime.utcnow()
                session.commit()
                self.logger.info(f"set report status to failed for report {report.id}")

    def generate(self, question, references):
        self.logger.info(f"generating answer for question: {question}")
        response = requests.post(
            self.llm_endpoint,
            headers={
                "Content-Type": "application/json",
            },
            json={
                "query": question,
                "references": references,
                "key": self.config.model_options.genai_key,
                "provider": self.config.model_options.llm_provider,
            },
        )

        if response.status_code != 200:
            self.logger.error(
                f"Not able to get generated answer for question {question} status_code: {response.status_code}"
            )
            return "error generating answer"

        self.logger.info(f"generated answer for question: {question}")
        return response.text

    def run(self, poll_interval: int = 5):
        self.logger.info("Starting ReportProcessorWorker...")

        while True:
            try:
                report = self.fetch_and_lock_pending_report()

                if not report:
                    self.logger.info("No pending reports. Sleeping...")
                    time.sleep(poll_interval)
                    continue

                self.process_report(report)

            except Exception as e:
                self.logger.error(f"Worker encountered an error: {e}")
                time.sleep(poll_interval)


if __name__ == "__main__":
    config: DeploymentConfig = load_config()

    setup_logger(
        Path(config.model_bazaar_dir) / "logs",
        f"knowledge_extraction_{config.model_id}",
    )

    worker = ReportProcessorWorker(config=config)
    worker.run()
