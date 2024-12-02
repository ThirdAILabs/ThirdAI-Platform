import json
import os
import shutil
import uuid
from datetime import datetime, timedelta
from logging import Logger
from pathlib import Path
from typing import List, Optional

from deployment_job.permissions import Permissions
from deployment_job.pydantic_models.inputs import DocumentList
from deployment_job.reporter import Reporter
from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from fastapi.encoders import jsonable_encoder
from platform_common.file_handler import download_local_files
from platform_common.knowledge_extraction.schema import Base, Keyword, Question, Report
from platform_common.pydantic_models.deployment import DeploymentConfig
from platform_common.utils import response
from pydantic import ValidationError
from sqlalchemy import and_, create_engine, or_
from sqlalchemy.orm import Session, scoped_session, sessionmaker

JOB_TOKEN = os.environ["JOB_TOKEN"]


def verify_job_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if auth_header.split(" ", 1)[1] != JOB_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return None


MAX_ATTEMPTS = 3
REPORT_TIMEOUT = timedelta(minutes=5)


class KnowledgeExtractionRouter:
    def __init__(self, config: DeploymentConfig, reporter: Reporter, logger: Logger):
        self.config = config
        self.logger = logger
        self.router = APIRouter()

        self.db_path = (
            Path(self.config.model_bazaar_dir)
            / "models"
            / config.model_id
            / "knowledge.db"
        )
        self.reports_base_path = (
            Path(self.config.model_bazaar_dir) / "models" / config.model_id / "reports"
        )

        self.reports_base_path.mkdir(parents=True, exist_ok=True)

        self.engine = self._initialize_db()
        self.Session = scoped_session(sessionmaker(bind=self.engine))

        self.router.add_api_route("/report/create", self.new_report, methods=["POST"])
        self.router.add_api_route(
            "/report/{report_id}", self.get_report, methods=["GET"]
        )
        self.router.add_api_route(
            "/report/{report_id}", self.delete_report, methods=["DELETE"]
        )
        self.router.add_api_route("/questions", self.add_question, methods=["POST"])
        self.router.add_api_route(
            "/questions", self.get_questions_public, methods=["GET"]
        )
        self.router.add_api_route(
            "/questions/{question_id}", self.delete_question, methods=["DELETE"]
        )
        self.router.add_api_route(
            "/questions/{question_id}/keywords", self.add_keywords, methods=["POST"]
        )

        self.router.add_api_route(
            "/questions-internal", self.get_questions_internal, methods=["GET"]
        )
        self.router.add_api_route(
            "/report/{report_id}/status", self.update_report_status, methods=["POST"]
        )
        self.router.add_api_route(
            "/report/next", self.next_unprocessed_report, methods=["POST"]
        )

    def _initialize_db(self):
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True)

        engine = create_engine(f"sqlite:///{self.db_path}")
        Base.metadata.create_all(engine)
        return engine

    def get_session(self) -> Session:
        return self.Session()

    def new_report(
        self,
        documents: str = Form(...),
        files: List[UploadFile] = [],
        _: str = Depends(Permissions.verify_permission("write")),
    ):
        try:
            documents = DocumentList.model_validate_json(documents).documents
        except ValidationError as e:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Invalid format for document report",
                data={"details": str(e), "documents": documents},
            )

        if not documents:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="No documents supplied for report. Must supply at least one document.",
            )

        report_id = str(uuid.uuid4())

        documents = download_local_files(
            files=files,
            file_infos=documents,
            dest_dir=self.reports_base_path / report_id / "documents",
        )

        with open(self.reports_base_path / report_id / "documents.json", "w") as file:
            json.dump([doc.model_dump() for doc in documents], file)

        with self.get_session() as session:
            new_report = Report(
                id=report_id,
                status="queued",
                submitted_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(new_report)
            session.commit()

        return response(
            status_code=status.HTTP_200_OK,
            message="Successfully submitted the documents to get the report, use the report_id to check the status.",
            data={"report_id": str(report_id)},
        )

    def get_report(
        self, report_id: str, _: str = Depends(Permissions.verify_permission("read"))
    ):
        with self.get_session() as session:
            report: Report = session.query(Report).get(report_id)

            if not report:
                return response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message=f"Report with ID '{report_id}' not found.",
                )

            report_data = {
                "report_id": report.id,
                "status": report.status,
                "submitted_at": report.submitted_at,
                "updated_at": report.updated_at,
            }

            if report.status == "complete":
                report_file_path = (
                    self.reports_base_path / report_id / f"report_{report.attempt}.json"
                )

                if not report_file_path.exists():
                    if report.status == "complete":
                        return response(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            message=f"Processed reports directory for ID '{report_id}' is missing.",
                        )

                try:
                    with open(report_file_path) as file:
                        report_data["content"] = json.load(file)
                except Exception as e:
                    self.logger.error(
                        f"Failed to read document report {report_file_path}: {e}"
                    )

                    return response(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        message=f"failed to load report content",
                    )

            return response(
                status_code=status.HTTP_200_OK,
                message="Successfully retrieved the report details.",
                data=jsonable_encoder(report_data),
            )

    def delete_report(
        self, report_id: str, _: str = Depends(Permissions.verify_permission("write"))
    ):
        with self.get_session() as session:
            report = session.query(Report).get(report_id)

            if not report:
                return response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message=f"Report with ID '{report_id}' not found.",
                )

            session.delete(report)
            session.commit()

        report_path = self.reports_base_path / report_id
        if report_path.exists() and report_path.is_dir():
            try:
                shutil.rmtree(report_path)
            except Exception as e:
                return response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=f"Failed to delete report files for ID '{report_id}'.",
                    data={"details": str(e)},
                )

        return response(
            status_code=status.HTTP_200_OK,
            message=f"Successfully deleted report with ID '{report_id}'.",
        )

    def add_question(
        self,
        question: str,
        keywords: Optional[List[str]] = None,
        _: str = Depends(Permissions.verify_permission("write")),
    ):
        try:
            with self.get_session() as session:
                duplicate_questions = (
                    session.query(Question)
                    .filter(Question.question_text.ilike(question))
                    .count
                )()
                if duplicate_questions > 0:
                    return response(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        message=f"Question '{question}' is a duplicate of an existing question.",
                    )

                new_question = Question(
                    id=str(uuid.uuid4()),
                    question_text=question,
                )
                session.add(new_question)
                session.commit()
                session.refresh(new_question)

                if keywords:
                    new_keyword = Keyword(
                        id=str(uuid.uuid4()),
                        question_id=new_question.id,
                        keyword_text=" ".join(keywords),
                    )
                    session.add(new_keyword)

                session.commit()

            return response(
                status_code=status.HTTP_200_OK,
                message="Successfully added questions and associated keywords.",
            )
        except Exception as e:
            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="An error occurred while adding questions.",
                data={"details": str(e)},
            )

    def get_questions(self):
        try:
            with self.get_session() as session:
                questions = session.query(Question).all()

                data = []
                for question in questions:
                    keywords = (
                        session.query(Keyword)
                        .filter(Keyword.question_id == question.id)
                        .all()
                    )
                    data.append(
                        {
                            "question_id": question.id,
                            "question_text": question.question_text,
                            "keywords": [keyword.keyword_text for keyword in keywords],
                        }
                    )

                return response(
                    status_code=status.HTTP_200_OK,
                    message="Successfully retrieved questions with associated keywords.",
                    data=data,
                )
        except Exception as e:
            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="An error occurred while retrieving questions.",
                data={"details": str(e)},
            )

    def get_questions_internal(self, _=Depends(verify_job_token)):
        return self.get_questions()

    def get_questions_public(
        self, _: str = Depends(Permissions.verify_permission("read"))
    ):
        return self.get_questions()

    def delete_question(
        self,
        question_id: str,
        _: str = Depends(Permissions.verify_permission("write")),
    ):
        try:
            with self.get_session() as session:
                question = session.query(Question).get(question_id)
                if not question:
                    return response(
                        status_code=status.HTTP_404_NOT_FOUND,
                        message=f"Question with ID '{question_id}' not found.",
                    )

                # Delete associated keywords
                session.query(Keyword).filter(
                    Keyword.question_id == question_id
                ).delete()

                # Delete the question itself
                session.delete(question)

                session.commit()

            return response(
                status_code=status.HTTP_200_OK,
                message="Successfully deleted the specified questions and their associated keywords.",
            )
        except Exception as e:
            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="An error occurred while deleting questions.",
                data={"details": str(e)},
            )

    def add_keywords(
        self,
        question_id: str,
        keywords: List[str],
        _: str = Depends(Permissions.verify_permission("write")),
    ):
        try:
            with self.get_session() as session:
                question = session.query(Question).get(question_id)
                if not question:
                    return response(
                        status_code=status.HTTP_404_NOT_FOUND,
                        message=f"Question '{question_id}' not found. Cannot add keywords.",
                    )

                session.add(
                    Keyword(
                        id=str(uuid.uuid4()),
                        question_id=question_id,
                        keyword_text=" ".join(keywords),
                    )
                )
                session.commit()

            return response(
                status_code=status.HTTP_200_OK,
                message="Successfully added keywords to the specified questions.",
            )
        except Exception as e:
            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="An error occurred while adding keywords.",
                data={"details": str(e)},
            )

    def next_unprocessed_report(self, _=Depends(verify_job_token)):
        try:
            self.logger.info("checking for unprocessed reports")
            with self.get_session() as session:
                report = (
                    session.query(Report)
                    .where(
                        or_(
                            Report.status == "queued",
                            and_(
                                Report.status == "in_progress",
                                Report.attempt < MAX_ATTEMPTS,
                                Report.updated_at
                                < (datetime.utcnow() - REPORT_TIMEOUT),
                            ),
                        )
                    )
                    .order_by(Report.submitted_at.asc())  # Process oldest first
                    .with_for_update(skip_locked=True)  # Lock row to prevent conflicts
                    .first()
                )
                if report:
                    self.logger.info(f"found unprocessed report: {report.id}")
                    report.status = "in_progress"
                    report.attempt += 1
                    report.updated_at = datetime.utcnow()
                    session.commit()

                    return response(
                        status_code=status.HTTP_200_OK,
                        message="found unprocessed report",
                        data={"report_id": report.id, "attempt": report.attempt},
                    )
                else:
                    self.logger.info("no unprocessed reports found")

                    return response(
                        status_code=status.HTTP_200_OK,
                        message="no unprocessed reports found",
                        data={"report_id": None, "attempt": None},
                    )

        except Exception as e:
            self.logger.error(f"error checking for unprocessed report: {e}")
            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="An error occurred while checking for unprocessed reports.",
                data={"details": str(e)},
            )

    def update_report_status(
        self, report_id: str, new_status: str, attempt: int, _=Depends(verify_job_token)
    ):
        try:
            with self.get_session() as session:
                report = session.query(Report).get(report_id)
                if not report:
                    return response(
                        status_code=status.HTTP_404_BAD_REQUEST,
                        message=f"report {report_id} not found",
                    )

                if report.attempt != attempt:
                    return response(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        message="invalid attempt number, this report has been assigned to a new worker",
                    )

                report.status = new_status
                report.updated_at = datetime.utcnow()
                session.commit()
                self.logger.info(
                    f"updated status of report {report_id} to {new_status}"
                )
                return response(
                    status_code=status.HTTP_200_OK,
                    message="updated report status",
                )
        except Exception as e:
            self.logger.error(
                f"error updating report status of {report_id} to {new_status}: {e}"
            )
            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="An error occurred while updating report status.",
                data={"details": str(e)},
            )
