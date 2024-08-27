from __future__ import annotations

import typing
from abc import abstractmethod
from collections import defaultdict

from data_types import (
    DataSamples,
    UserFeedBack,
    deserialize_sample_datatype,
    deserialize_userfeedback,
)
from schemas import Base, FeedBack, Samples
from sqlalchemy import create_engine, event, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import scoped_session, sessionmaker


# turns on foreign key constraint check for sqlite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Connector:
    # Interface for data store backend. Can be repurposed to a DB based storage,
    # a file based storage, etc. The DataStore should be persistent.
    @abstractmethod
    def add_samples(self, entries: typing.List[typing.tuple[str, str, str, str]]):
        # batch insertion of samples to the store
        pass

    @abstractmethod
    def add_feedback(self, entries: typing.List[typing.tuple[str, str, str]]):
        # batch insertion of user feedback to the store
        pass

    @abstractmethod
    def get_sample_count(self, name: str, with_feedback: bool):
        # returns the total count of entries with the given name
        # with feedback : None - returns total count
        # with feedback : True - returns samples with a feedback associated to them
        # with feedback : False - returns samples with no feedback associated to them
        pass

    @abstractmethod
    def get_feedback_count(self, name: str):
        pass

    @abstractmethod
    def delete_old_samples(self, name: str, samples_to_store: int):
        # sort the entries by timestamp and deletes the oldest k entries
        pass

    @abstractmethod
    def get_samples(self, name: str, num_samples: int):
        # get num_entries entries with a specific name
        pass

    @abstractmethod
    def get_feedback(self, name: str):
        pass

    @abstractmethod
    def existing_sample_names(self):
        # get unique names in the store
        pass


class SQLiteConnector(Connector):
    def __init__(self, db_path: str):
        self.engine = create_engine(f"sqlite:///{db_path}", echo=True)
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        Base.metadata.create_all(self.engine)

    def add_samples(self, entries: typing.List[typing.Tuple[str, str, str, str]]):
        session = self.Session()
        session.bulk_insert_mappings(
            Samples,
            [
                {
                    "id": unique_id,
                    "datatype": datatype,
                    "name": name,
                    "serialized_data": data,
                }
                for unique_id, datatype, name, data in entries
            ],
        )
        session.commit()

    def add_feedback(self, entries: typing.List[typing.Tuple[str, str]]):
        session = self.Session()
        session.bulk_insert_mappings(
            FeedBack,
            [
                {
                    "sample_uuid": sample_uuid,
                    "serialized_data": data,
                }
                for sample_uuid, data in entries
            ],
        )
        session.commit()

    def get_sample_count(self, name: str, with_feedback: bool = None):

        session = self.Session()
        if with_feedback is None:
            return (
                session.query(func.count(Samples.id))
                .filter(Samples.name == name)
                .scalar()
            )

        if with_feedback:
            return (
                session.query(func.count(Samples.id))
                .join(FeedBack, Samples.id == FeedBack.sample_uuid)
                .filter(Samples.name == name)
                .scalar()
            )

        return (
            session.query(func.count(Samples.id))
            .outerjoin(FeedBack, Samples.id == FeedBack.sample_uuid)
            .filter(Samples.name == name)
            .filter(FeedBack.id == None)
            .scalar()
        )

    def get_feedback_count(self, name: str):
        session = self.Session()
        count = (
            session.query(func.count(FeedBack.id))
            .join(Samples)
            .filter(Samples.name == name)
            .scalar()
        )
        return count

    def delete_old_samples(self, name: str, samples_to_store: int):
        # only delete samples that have no feedback associated with them
        samples_without_feedback = self.get_sample_count(name, with_feedback=False)

        # total samples
        total_samples = self.get_sample_count(name)

        samples_to_delete = total_samples - samples_to_store

        if samples_to_delete > 0 and samples_without_feedback > 0:
            session = self.Session()

            # delete only the samples that have no associated feedback
            oldest_entries = (
                session.query(Samples.id)
                .outerjoin(FeedBack, Samples.id == FeedBack.sample_uuid)
                .filter(Samples.name == name)
                .filter(FeedBack.id == None)
                .order_by(Samples.timestamp.asc())
                .limit(samples_to_delete)
                .all()
            )

            for entry_id in oldest_entries:
                session.delete(session.query(Samples).get(entry_id[0]))
            session.commit()

    def get_samples(self, name: str, num_samples: int):
        session = self.Session()
        entries = (
            session.query(Samples.datatype, Samples.id, Samples.serialized_data)
            .filter(Samples.name == name)
            .order_by(Samples.timestamp.desc())
            .limit(num_samples)
            .all()
        )
        return entries

    def get_feedback(self, name: str):
        session = self.Session()
        entries = (
            session.query(
                Samples.datatype, FeedBack.sample_uuid, FeedBack.serialized_data
            )
            .join(Samples)
            .filter(Samples.name == name)
            .order_by(FeedBack.timestamp.desc())
            .all()
        )
        return entries

    def existing_sample_names(self):
        session = self.Session()
        names = session.query(Samples.name).distinct().all()

        return set([name[0] for name in names])


class DataStorage:
    def __init__(self, connector: Connector):
        # all class attributes should be generated using the connector
        # and it is supposed to be used as a single source of truth.
        self.connector = connector

        # this counter is local to DataStorage and will not be consistent across different instances of DataStorage.
        # this reduces the write load on the Connector. the number of samples for the same storage might end up being
        # more than the buffer limit but they can be clipped out later.
        self._sample_counter = defaultdict(int)
        for name in self.connector.existing_sample_names():
            self._sample_counter[name] = connector.get_sample_count(
                name=name, with_feedback=None
            )

        # if per name buffer size is None then no limit on the number of samples for each name
        # this attribute is to be considered as private so that two different instances of
        # DataStorage with the same connector have same buffer size.
        self._per_name_buffer_size = 1000

    def insert_samples(
        self, samples: typing.List[DataSamples], override_buffer_limit=False
    ):
        samples_to_insert = []
        for sample in samples:
            if override_buffer_limit or (
                self._per_name_buffer_size
                and self._sample_counter[sample.name] < self._per_name_buffer_size
            ):
                samples_to_insert.append(
                    (sample.uuid, sample.datatype, sample.name, sample.serialize())
                )

                self._sample_counter[sample.name] += 1

        self.connector.add_samples(samples_to_insert)

    def retrieve_samples(self, name: str, num_samples: int):
        entries = self.connector.get_samples(name, num_samples=num_samples)

        return [
            deserialize_sample_datatype(
                type=datatype, unique_id=unique_id, name=name, serialized_data=data
            )
            for datatype, unique_id, data in entries
        ]

    def insert_feedbacks(self, feedbacks: typing.List[UserFeedBack]):
        feedbacks_to_insert = []

        for feedback in feedbacks:
            feedbacks_to_insert.append((feedback.sample_uuid, feedback.serialize()))

        self.connector.add_feedback(feedbacks_to_insert)

    def retrieve_feedbacks(self, name: str):
        feedbacks = self.connector.get_feedback(name)

        return [
            deserialize_userfeedback(
                type=datatype, sample_uuid=sample_uuid, name=name, serialized_data=data
            )
            for datatype, sample_uuid, data in feedbacks
        ]

    def clip_storage(self):
        existing_sample_types = self.connector.existing_sample_names()

        for name in existing_sample_types:
            # only deletes samples with no feedback associated with them
            self.connector.delete_old_samples(
                name=name, samples_to_store=self._per_name_buffer_size
            )

            # update the sample counter
            self._sample_counter[name] = self.connector.get_sample_count(
                name=name, with_feedback=None
            )
