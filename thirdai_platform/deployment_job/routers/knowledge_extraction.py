import shutil
import uuid
from datetime import datetime
from logging import Logger
from pathlib import Path
from typing import List

from deployment_job.permissions import Permissions
from deployment_job.pydantic_models.inputs import DocumentList
from fastapi import APIRouter, Body, Depends, Form, UploadFile, status
from fastapi.encoders import jsonable_encoder
from platform_common.file_handler import download_local_files
from platform_common.knowledge_extraction.schema import Base, Keyword, Question, Report
from platform_common.pydantic_models.deployment import DeploymentConfig
from platform_common.pydantic_models.training import QuestionKeywords
from platform_common.utils import response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker


class KnowledgeExtractionRouter:
    def __init__(self, config: DeploymentConfig, logger: Logger):
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

        self.router.add_api_route("/new-report", self.new_report, methods=["POST"])
        self.router.add_api_route("/get-report", self.get_report, methods=["GET"])
        self.router.add_api_route(
            "/delete-report", self.delete_report, methods=["POST"]
        )
        self.router.add_api_route(
            "/add-questions", self.add_questions, methods=["POST"]
        )
        self.router.add_api_route("/get-questions", self.get_questions, methods=["GET"])
        self.router.add_api_route(
            "/delete-questions", self.delete_questions, methods=["POST"]
        )
        self.router.add_api_route("/add-keywords", self.add_keywords, methods=["POST"])
        self.router.add_api_route(
            "/delete-keywords", self.delete_keywords, methods=["POST"]
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

        with self.get_session() as session:
            new_report = Report(
                id=report_id,
                status="queued",
                submitted_at=datetime.utcnow(),
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
                report_file_path = self.reports_base_path / report_id / "report.jsonl"
                if not report_file_path.exists():
                    return response(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        message=f"Report file for ID '{report_id}' is missing.",
                    )

                try:
                    with report_file_path.open("r") as file:
                        report_contents = [line.strip() for line in file.readlines()]
                    report_data["contents"] = report_contents
                except Exception as e:
                    return response(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        message=f"Failed to read report file for ID '{report_id}'.",
                        data={"details": str(e)},
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

    def add_questions(
        self,
        questions: List[QuestionKeywords] = Body(...),
        _: str = Depends(Permissions.verify_permission("write")),
    ):
        try:
            with self.get_session() as session:
                for question_item in questions:
                    new_question = Question(
                        id=str(uuid.uuid4()),
                        question_text=question_item.question,
                    )
                    session.add(new_question)
                    session.commit()
                    session.refresh(new_question)

                    if question_item.keywords:
                        for keyword_text in question_item.keywords:
                            new_keyword = Keyword(
                                id=str(uuid.uuid4()),
                                question_id=new_question.id,
                                keyword_text=keyword_text,
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

    def get_questions(self, _: str = Depends(Permissions.verify_permission("read"))):
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

    def delete_questions(
        self,
        question_ids: List[str] = Body(
            ..., description="List of question IDs to delete."
        ),
        _: str = Depends(Permissions.verify_permission("write")),
    ):
        try:
            with self.get_session() as session:
                for question_id in question_ids:
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
        keywords_data: List[QuestionKeywords] = Body(
            ..., description="List of questions and their associated keywords."
        ),
        _: str = Depends(Permissions.verify_permission("write")),
    ):
        try:
            with self.get_session() as session:
                for item in keywords_data:
                    question = (
                        session.query(Question)
                        .filter(Question.question_text == item.question)
                        .first()
                    )
                    if not question:
                        return response(
                            status_code=status.HTTP_404_NOT_FOUND,
                            message=f"Question '{item.question}' not found. Cannot add keywords.",
                        )

                    if item.keywords:
                        for keyword_text in item.keywords:
                            existing_keyword = (
                                session.query(Keyword)
                                .filter(
                                    Keyword.question_id == question.id,
                                    Keyword.keyword_text == keyword_text,
                                )
                                .first()
                            )
                            if not existing_keyword:
                                new_keyword = Keyword(
                                    id=str(uuid.uuid4()),
                                    question_id=question.id,
                                    keyword_text=keyword_text,
                                )
                                session.add(new_keyword)

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

    def delete_keywords(
        self,
        question_id: str = Form(
            ..., description="The ID of the question whose keywords need to be deleted."
        ),
        keywords: List[str] = Form(
            default=None,
            description="A list of keywords to delete. If not provided, all keywords for the question will be deleted.",
        ),
        _: str = Depends(Permissions.verify_permission("write")),
    ):
        try:
            with self.get_session() as session:
                db_question = session.query(Question).get(question_id)

                if not db_question:
                    return response(
                        status_code=status.HTTP_404_NOT_FOUND,
                        message=f"Question with ID '{question_id}' not found.",
                    )

                if keywords:
                    deleted_count = (
                        session.query(Keyword)
                        .filter(
                            Keyword.question_id == question_id,
                            Keyword.keyword_text.in_(keywords),
                        )
                        .delete(synchronize_session=False)
                    )
                else:
                    deleted_count = (
                        session.query(Keyword)
                        .filter_by(question_id=question_id)
                        .delete(synchronize_session=False)
                    )

                session.commit()

                if deleted_count == 0:
                    return response(
                        status_code=status.HTTP_404_NOT_FOUND,
                        message="No matching keywords found for deletion.",
                    )

                return response(
                    status_code=status.HTTP_200_OK,
                    message=f"Successfully deleted {deleted_count} keyword(s) for question with ID '{question_id}'.",
                )
        except Exception as e:
            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="An error occurred while deleting keywords.",
                data={"details": str(e)},
            )
