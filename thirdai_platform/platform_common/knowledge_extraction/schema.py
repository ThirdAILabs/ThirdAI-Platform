from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True)
    status = Column(String, nullable=False)
    submitted_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    attempt = Column(Integer, default=0, nullable=False)


class Question(Base):
    __tablename__ = "questions"

    id = Column(String, primary_key=True)
    question_text = Column(Text, nullable=False, unique=True)
    keywords = relationship("Keyword", back_populates="question")


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(String, primary_key=True)
    question_id = Column(String, ForeignKey("questions.id"), nullable=False)
    keyword_text = Column(Text, nullable=False)
    question = relationship("Question", back_populates="keywords")


def get_knowledge_db_session(db_path: str):
    """Dynamically create a session for the knowledge extraction database."""
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal
