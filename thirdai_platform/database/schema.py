import enum
import re
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import declarative_base, relationship, validates

SQLDeclarativeBase = declarative_base()


class Status(str, enum.Enum):
    not_started = "not_started"
    starting = "starting"
    in_progress = "in_progress"
    stopped = "stopped"
    complete = "complete"
    failed = "failed"


class Access(str, enum.Enum):
    public = "public"
    protected = "protected"
    private = "private"


class User(SQLDeclarativeBase):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(254), nullable=False, unique=True)
    password_hash = Column(
        String, nullable=True
    )  # If NULL then its verified from some of the OAuth providers.
    verified = Column(Boolean, default=False)
    verification_token = Column(
        UUID(as_uuid=True),
        unique=True,
        server_default=text("gen_random_uuid()"),
    )

    models = relationship("Model", back_populates="user", cascade="all, delete-orphan")
    deployments = relationship(
        "Deployment", back_populates="user", cascade="all, delete-orphan"
    )
    logs = relationship("Log", back_populates="user", cascade="all, delete-orphan")

    @validates("username")
    def validate_username(self, key, username):
        # allow only alphanumeric characters, underscores, and hyphens
        assert re.match(
            r"^[\w-]+$", username
        ), "Username should only contain alphanumeric characters, underscores, and hyphens"
        return username

    @property
    def domain(self) -> str:
        return self.email.split("@")[1]


class Model(SQLDeclarativeBase):
    __tablename__ = "models"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name = Column(String, nullable=False)
    train_status = Column(ENUM(Status), nullable=False, default=Status.not_started)
    type = Column(String(256), nullable=False)
    sub_type = Column(String(256), nullable=True)
    downloads = Column(Integer, nullable=False, default=0)
    access_level = Column(ENUM(Access), nullable=False, default=Access.private)
    domain = Column(String, nullable=True)
    published_date = Column(
        DateTime, default=datetime.utcnow().isoformat(), nullable=True
    )

    parent_id = Column(
        UUID(as_uuid=True), ForeignKey("models.id", ondelete="SET NULL"), nullable=True
    )  # Not null if this model comes from starting training from a base model

    parent_deployment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="SET NULL"),
        nullable=True,
    )  # Not null if this model comes from saving a deployment session

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    user = relationship("User", back_populates="models")

    parent_deployment = relationship(
        "Deployment", back_populates="child_models", foreign_keys=[parent_deployment_id]
    )

    deployments = relationship(
        "Deployment", back_populates="model", foreign_keys="[Deployment.model_id]"
    )

    meta_data = relationship(
        "MetaData", back_populates="model", uselist=False, cascade="all, delete-orphan"
    )

    model_shards = relationship(
        "ModelShard", back_populates="model", cascade="all, delete-orphan"
    )

    @validates("name")
    def validate_model_name(self, key, name):
        # allow only alphanumeric characters, underscores, and hyphens
        assert re.match(
            r"^[\w-]+$", name
        ), "Model name should only contain alphanumeric characters, underscores, and hyphens"
        return name

    __table_args__ = (
        Index("train_status_index", "train_status"),
        Index("model_identifier_index", "user_id", "name"),
        UniqueConstraint("user_id", "name"),
    )


class MetaData(SQLDeclarativeBase):
    __tablename__ = "metadata"

    general = Column(JSON, nullable=True)
    train = Column(JSON, nullable=True)

    model_id = Column(
        UUID(as_uuid=True),
        ForeignKey("models.id", ondelete="CASCADE"),
        primary_key=True,
    )

    model = relationship("Model", back_populates="meta_data")


class ModelShard(SQLDeclarativeBase):
    __tablename__ = "model_shards"

    shard_num = Column(Integer, primary_key=True, nullable=False)
    train_status = Column(ENUM(Status), nullable=False, default=Status.not_started)

    model_id = Column(
        UUID(as_uuid=True),
        ForeignKey("models.id", ondelete="CASCADE"),
        primary_key=True,
    )

    model = relationship("Model", back_populates="model_shards")


class Deployment(SQLDeclarativeBase):
    __tablename__ = "deployments"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name = Column(String(256), nullable=False)
    status = Column(ENUM(Status), nullable=False)

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    model_id = Column(
        UUID(as_uuid=True),
        ForeignKey("models.id", ondelete="CASCADE"),
        nullable=False,
    )

    metadata_json = Column(JSON, nullable=True)

    child_models = relationship(
        "Model",
        back_populates="parent_deployment",
        foreign_keys=[Model.parent_deployment_id],
    )

    user = relationship("User", back_populates="deployments")
    model = relationship("Model", back_populates="deployments", foreign_keys=[model_id])
    logs = relationship(
        "Log", back_populates="deployment", cascade="all, delete-orphan"
    )

    @validates("name")
    def validate_deployment_name(self, key, name):
        # allow only alphanumeric characters, underscores, and hyphens
        assert re.match(
            r"^[\w-]+$", name
        ), "Deployment name should only contain alphanumeric characters, underscores, and hyphens"
        return name

    __table_args__ = (UniqueConstraint("model_id", "user_id", "name"),)


class Log(SQLDeclarativeBase):
    __tablename__ = "logs"

    deployment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    action = Column(String, primary_key=True)
    count = Column(Integer, nullable=False, default=0)
    log_entries = Column(JSON, nullable=True)

    deployment = relationship("Deployment", back_populates="logs")
    user = relationship("User", back_populates="logs")

    __table_args__ = (
        Index("log_deployment_index", "deployment_id"),
        Index("log_user_index", "user_id"),
        UniqueConstraint(
            "deployment_id", "user_id", "action", name="unique_deployment_user_action"
        ),
    )
