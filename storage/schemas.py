from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Samples(Base):
    __tablename__ = "samples"
    id = Column(String(36), primary_key=True, index=True)
    datatype = Column(String)
    name = Column(String, index=True)
    serialized_data = Column(String)
    timestamp = Column(DateTime, default=func.current_timestamp())

    feedback_entries = relationship("FeedBack", back_populates="sample")


class FeedBack(Base):
    __tablename__ = "user_feedback"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_uuid = Column(String(36), ForeignKey("samples.id"), nullable=False)
    sample = relationship("Samples", back_populates="feedback_entries")

    serialized_data = Column(String)
    timestamp = Column(DateTime, default=func.current_timestamp())
