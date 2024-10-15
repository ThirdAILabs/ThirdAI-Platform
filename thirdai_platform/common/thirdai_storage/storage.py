from __future__ import annotations

import typing
from abc import abstractmethod
from collections import defaultdict

from sqlalchemy import create_engine, func
from sqlalchemy.orm import scoped_session, sessionmaker

from .data_types import DataSample, Metadata, MetadataStatus, SampleStatus
from .schemas import Base, MetaData, Samples


class Connector:
    # Interface for data store backend. Can be repurposed to a DB based storage,
    # a file based storage, etc. The DataStore should be persistent.
    @abstractmethod
    def add_samples(self, entries: typing.List[typing.tuple[str, str, str, str, bool]]):
        # batch insertion of samples to the store
        pass

    @abstractmethod
    def get_sample_count(self, name: str):
        # returns the total count of entries with the given name
        pass

    @abstractmethod
    def delete_old_samples(self, name: str, samples_to_store: int):
        # sort the entries by timestamp and deletes the oldest k entries
        pass

    @abstractmethod
    def get_samples(self, name: str, num_samples: int, user_provided: bool):
        # get num_entries entries with a specific name
        pass

    @abstractmethod
    def existing_sample_names(self):
        # get unique names in the store
        pass

    @abstractmethod
    def insert_metadata(self, name: str, datatype: str, serialized_data: str):
        # if an entry with the value name exists, updates its serialized data,
        # else makes a new entry for the metadata in the DB.
        pass

    @abstractmethod
    def get_metadata(self, name: str):
        pass

    @abstractmethod
    def remove_untrained_samples(self, name: str):
        pass


class SQLiteConnector(Connector):
    def __init__(self, db_path: str):
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        Base.metadata.create_all(self.engine)

    def add_samples(
        self, entries: typing.List[typing.Tuple[str, str, str, str, str, bool]]
    ):
        session = self.Session()
        session.bulk_insert_mappings(
            Samples,
            [
                {
                    "id": unique_id,
                    "datatype": datatype,
                    "name": name,
                    "serialized_data": data,
                    "status": status,
                    "user_provided": user_provided,
                }
                for unique_id, datatype, name, data, status, user_provided in entries
            ],
        )
        session.commit()

    def get_sample_count(self, name: str):

        session = self.Session()

        return (
            session.query(func.count(Samples.id)).filter(Samples.name == name).scalar()
        )

    def delete_old_samples(self, name: str, samples_to_store: int):
        # total samples
        total_samples = self.get_sample_count(name)

        samples_to_delete = total_samples - samples_to_store

        if samples_to_delete > 0:
            session = self.Session()
            oldest_entries = (
                session.query(Samples.id)
                .filter(Samples.name == name)
                .filter(Samples.user_provided == False)
                .order_by(Samples.timestamp.asc())
                .limit(samples_to_delete)
                .all()
            )

            for entry_id in oldest_entries:
                session.delete(session.query(Samples).get(entry_id[0]))
            session.commit()

    def get_samples(self, name: str, num_samples: int, user_provided: bool):
        session = self.Session()
        entries = (
            session.query(
                Samples.datatype,
                Samples.id,
                Samples.serialized_data,
                Samples.status,
            )
            .filter(Samples.name == name)
            .filter(Samples.user_provided == user_provided)
            .order_by(Samples.timestamp.desc())
            .limit(num_samples)
            .all()
        )
        return entries

    def existing_sample_names(self):
        session = self.Session()
        names = session.query(Samples.name).distinct().all()

        return set([name[0] for name in names])

    def insert_metadata(
        self, name: str, status: str, datatype: str, serialized_data: str
    ):
        session = self.Session()

        existing_metadata = (
            session.query(MetaData).filter(MetaData.name == name).first()
        )
        if existing_metadata:
            # update the entry in place
            existing_metadata.serialized_data = serialized_data
            existing_metadata.status = status
        else:
            new_metadata = MetaData(
                name=name,
                datatype=datatype,
                serialized_data=serialized_data,
                status=status,
            )
            session.add(new_metadata)

        session.commit()

    def get_metadata(self, name: str):
        session = self.Session()

        entry = (
            session.query(
                MetaData.datatype,
                MetaData.name,
                MetaData.serialized_data,
                MetaData.status,
            )
            .filter(MetaData.name == name)
            .first()
        )
        return entry

    def remove_untrained_samples(self, name: str):
        # remove all untrained samples for a given name
        session = self.Session()
        session.query(Samples).filter(Samples.name == name).filter(
            Samples.status == SampleStatus.untrained
        ).delete()
        session.commit()

    def update_metadata_status(self, name: str, status: MetadataStatus):
        session = self.Session()
        session.query(MetaData).filter(MetaData.name == name).update(
            {MetaData.status: status}
        )
        session.commit()

    def update_sample_status(self, name: str, status: SampleStatus):
        session = self.Session()
        session.query(Samples).filter(Samples.name == name).update(
            {Samples.status: status}
        )
        session.commit()


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
            self._sample_counter[name] = connector.get_sample_count(name=name)

        # if per name buffer size is None then no limit on the number of samples for each name
        # this attribute is to be considered as private so that two different instances of
        # DataStorage with the same connector have same buffer size.
        self._per_name_buffer_size = 100000

    def insert_samples(
        self, samples: typing.List[DataSample], override_buffer_limit=False
    ):
        samples_to_insert = []
        for sample in samples:
            if override_buffer_limit or (
                self._per_name_buffer_size
                and self._sample_counter[sample.name] < self._per_name_buffer_size
            ):
                samples_to_insert.append(
                    (
                        sample.unique_id,
                        sample.datatype,
                        sample.name,
                        sample.serialize_data(),
                        sample.status.value,
                        sample.user_provided,
                    )
                )

                self._sample_counter[sample.name] += 1

        self.connector.add_samples(samples_to_insert)

    def retrieve_samples(self, name: str, num_samples: int, user_provided: bool):
        entries = self.connector.get_samples(
            name, num_samples=num_samples, user_provided=user_provided
        )

        return [
            DataSample.from_serialized(
                type=datatype,
                unique_id=unique_id,
                name=name,
                serialized_data=data,
                status=status,
                user_provided=user_provided,
            )
            for datatype, unique_id, data, status in entries
        ]

    def clip_storage(self):
        existing_sample_types = self.connector.existing_sample_names()

        for name in existing_sample_types:
            self.connector.delete_old_samples(
                name=name, samples_to_store=self._per_name_buffer_size
            )

            # update the sample counter
            self._sample_counter[name] = self.connector.get_sample_count(name=name)

    def insert_metadata(self, metadata: Metadata):
        # updates the serialized data in place if another entry with the same
        # name exists
        self.connector.insert_metadata(
            name=metadata.name,
            status=metadata.status,
            datatype=metadata.datatype,
            serialized_data=metadata.serialize_data(),
        )

    def get_metadata(self, name) -> Metadata:
        data = self.connector.get_metadata(name)
        if data:
            return Metadata.from_serialized(
                type=data[0], name=data[1], serialized_data=data[2], status=data[3]
            )

        return None

    def remove_untrained_samples(self, name: str):
        self.connector.remove_untrained_samples(name)

    def rollback_metadata(self, name: str):
        metadata = self.get_metadata(name)

        if metadata.status == MetadataStatus.updated:
            metadata.rollback()
            self.insert_metadata(metadata)

    def update_metadata_status(self, name: str, status: MetadataStatus):
        self.connector.update_metadata_status(name, status)

    def update_sample_status(self, name: str, status: SampleStatus):
        self.connector.update_sample_status(name, status)
