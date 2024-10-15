import os
import time
import typing
from abc import abstractmethod
from pathlib import Path
from typing import List

import pandas as pd
import thirdai
from config import (
    FileInfo,
    TextClassificationOptions,
    TokenClassificationOptions,
    TrainConfig,
    UDTTrainOptions,
)
from exceptional_handler import apply_exception_handler
from models.model import Model
from reporter import Reporter
from thirdai import bolt
from utils import (
    check_csv_only,
    check_local_nfs_only,
    expand_s3_buckets_and_directories,
)

from thirdai_platform.common.thirdai_storage.data_types import (
    DataSample,
    LabelEntity,
    LabelStatus,
    Metadata,
    MetadataStatus,
    SampleStatus,
    TagMetadata,
)
from thirdai_platform.common.thirdai_storage.storage import DataStorage, SQLiteConnector


@apply_exception_handler
class ClassificationModel(Model):
    report_failure_method = "report_status"

    @property
    def model_save_path(self) -> Path:
        return self.model_dir / "model.udt"

    @property
    def train_options(self) -> UDTTrainOptions:
        return self.config.model_options.train_options

    def supervised_files(self) -> List[FileInfo]:
        all_files = expand_s3_buckets_and_directories(self.config.data.supervised_files)
        check_csv_only(all_files)
        check_local_nfs_only(all_files)
        return all_files

    def test_files(self) -> List[FileInfo]:
        all_files = expand_s3_buckets_and_directories(self.config.data.test_files)
        check_csv_only(all_files)
        check_local_nfs_only(all_files)
        return all_files

    @abstractmethod
    def initialize_model(self):
        pass

    def get_size(self):
        """
        Calculate the size of the model in bytes
        """
        return self.model_save_path.stat().st_size

    def get_num_params(self, model: bolt.UniversalDeepTransformer) -> int:
        """
        Gets the number of parameters in the model

        Args:
            model: (bolt.UniversalDeepTransformer): The UDT instance
        Returns:
            int: The number of parameters in the model.

        """

        num_params = model._get_model().num_params()
        self.logger.info(f"Number of parameters in the model: {num_params}")
        return num_params

    @abstractmethod
    def get_latency(self):
        pass

    def get_udt_path(self, model_id):
        return Path(self.config.model_bazaar_dir) / "models" / model_id / "model.udt"

    def load_model(self, model_id):
        return bolt.UniversalDeepTransformer.load(str(self.get_udt_path(model_id)))

    def save_model(self, model):
        model.save(str(self.model_save_path))

    def get_model(self):
        # if a model with the same id has already been initialized, return the model
        if os.path.exists(self.model_save_path):
            return bolt.UniversalDeepTransformer.load(str(self.model_save_path))

        # if model with the id not found but has a base model, return the base model
        if self.config.base_model_id:
            return self.load_model(self.config.base_model_id)

        # initialize the model from scratch if the model does not exist or if there is not base model
        return self.initialize_model()

    def evaluate(self, model, test_files: List[FileInfo]):
        for test_file in test_files:
            model.evaluate(
                test_file.path, metrics=self.train_options.validation_metrics
            )

    @abstractmethod
    def train(self, **kwargs):
        pass


@apply_exception_handler
class TextClassificationModel(ClassificationModel):
    @property
    def txt_cls_vars(self) -> TextClassificationOptions:
        return self.config.model_options.udt_options

    def initialize_model(self):
        return bolt.UniversalDeepTransformer(
            data_types={
                self.txt_cls_vars.text_column: bolt.types.text(),
                self.txt_cls_vars.label_column: bolt.types.categorical(
                    n_classes=self.txt_cls_vars.n_target_classes
                ),
            },
            target=self.txt_cls_vars.label_column,
            delimiter=self.txt_cls_vars.delimiter,
        )

    def train(self, **kwargs):
        self.reporter.report_status(self.config.model_id, "in_progress")

        model = self.get_model()

        start_time = time.time()
        for train_file in self.supervised_files():
            model.train(
                train_file.path,
                epochs=self.train_options.supervised_epochs,
                learning_rate=self.train_options.learning_rate,
                batch_size=self.train_options.batch_size,
                metrics=self.train_options.metrics,
            )
        training_time = time.time() - start_time

        self.save_model(model)

        self.evaluate(model, self.test_files())

        num_params = self.get_num_params(model)
        model_size = self.get_size()
        model_size_in_memory = model_size * 4
        latency = self.get_latency(model)

        self.reporter.report_complete(
            self.config.model_id,
            metadata={
                "num_params": str(num_params),
                "thirdai_version": str(thirdai.__version__),
                "training_time": str(training_time),
                "size": str(model_size),
                "size_in_memory": str(model_size_in_memory),
                "latency": str(latency),
            },
        )

    def get_latency(self, model) -> float:
        self.logger.info("Measuring latency of the UDT instance.")

        start_time = time.time()
        model.predict({self.txt_cls_vars.text_column: "Checking for latency"}, top_k=1)
        latency = time.time() - start_time

        self.logger.info(f"Latency measured: {latency} seconds.")
        return latency


@apply_exception_handler
class TokenClassificationModel(ClassificationModel):
    def __init__(self, config: TrainConfig, reporter: Reporter):
        super().__init__(config, reporter)
        self.load_storage()

    @property
    def tkn_cls_vars(self) -> TokenClassificationOptions:
        return self.config.model_options.udt_options

    def initialize_model(self):
        # remove duplicates from target_labels
        target_labels = list(set(self.tkn_cls_vars.target_labels))

        # insert the tags into the storage to keep track of their training status
        tag_status = {
            self.tkn_cls_vars.default_tag: LabelEntity(
                name=self.tkn_cls_vars.default_tag, status=LabelStatus.untrained
            )
        }

        new_tags = self.config.datagen_options.datagen_options.tags
        for tag in new_tags:
            tag.status = LabelStatus.untrained
            tag_status[tag.name] = tag

        self.update_tag_metadata(
            tag_metadata=TagMetadata(tag_status=tag_status),
            status=MetadataStatus.unchanged,
        )

        default_tag = self.tkn_cls_vars.default_tag
        return bolt.UniversalDeepTransformer(
            data_types={
                self.tkn_cls_vars.source_column: bolt.types.text(),
                self.tkn_cls_vars.target_column: bolt.types.token_tags(
                    tags=target_labels,
                    default_tag=default_tag,
                ),
            },
            target=self.tkn_cls_vars.target_column,
        )

    def load_storage(self):
        data_storage_path = self.data_dir / "data_storage.db"
        # connector will instantiate an sqlite db at the specified path if it doesn't exist
        self.data_storage = DataStorage(
            connector=SQLiteConnector(db_path=data_storage_path)
        )

    @property
    def tag_metadata(self) -> TagMetadata:
        # load tags and their status from the storage
        return self.data_storage.get_metadata("tags_and_status").data

    def update_tag_metadata(self, tag_metadata, status: MetadataStatus):
        self.data_storage.insert_metadata(
            metadata=Metadata(name="tags_and_status", data=tag_metadata, status=status)
        )

    def train(self, **kwargs):
        self.reporter.report_status(self.config.model_id, "in_progress")

        model = self.get_model()

        start_time = time.time()

        supervised_files = self.supervised_files()
        # insert samples into data storage for later use
        self.insert_samples_in_storage(supervised_files)

        tags = self.tag_metadata

        # new labels to add to the model
        new_labels = []
        for name in tags.tag_status.keys():
            label = tags.tag_status[name]
            if label.status == LabelStatus.uninserted:
                new_labels.append(name)
                label.status = LabelStatus.trained

        if new_labels:
            model.add_ner_entities(new_labels)

        for train_file in self.supervised_files():
            model.train(
                train_file.path,
                epochs=self.train_options.supervised_epochs,
                learning_rate=self.train_options.learning_rate,
                batch_size=self.train_options.batch_size,
                metrics=self.train_options.metrics,
            )
        training_time = time.time() - start_time

        self.save_model(model)

        # converts the status of all tags to trained and update in the storage
        for tag in tags.tag_status:
            tags.tag_status[tag].status = LabelStatus.trained

        # once training is complete, update the status of the metadata to unchanged
        # and the status of the samples to trained
        self.update_tag_metadata(tags, MetadataStatus.unchanged)
        self.data_storage.update_sample_status("ner", SampleStatus.trained)

        self.evaluate(model, self.test_files())

        num_params = self.get_num_params(model)
        model_size = self.get_size()
        model_size_in_memory = model_size * 4
        latency = self.get_latency(model)

        self.reporter.report_complete(
            self.config.model_id,
            metadata={
                "num_params": str(num_params),
                "thirdai_version": str(thirdai.__version__),
                "training_time": str(training_time),
                "size": str(model_size),
                "size_in_memory": str(model_size_in_memory),
                "latency": str(latency),
            },
        )

    def insert_samples_in_storage(
        self, supervised_files: typing.List[FileInfo], buffer_size=50_000
    ):
        # these samples will be used as balancing samples for the training of the model
        # this sampling is not uniform but we assume that there won't be many samples
        # TODO(Shubh) : make this sampling uniform using reservoir sampling
        df = pd.DataFrame()
        for supervised_file in supervised_files:
            new_df = pd.read_csv(supervised_file.path)
            new_df = new_df[
                [self.tkn_cls_vars.source_column, self.tkn_cls_vars.target_column]
            ]

            df = pd.concat([df, new_df])
            df = df.sample(n=min(len(df), buffer_size))

        samples = []

        for index in df.index:
            row = df.loc[index]
            tokens = row[self.tkn_cls_vars.source_column].split()
            tags = row[self.tkn_cls_vars.target_column].split()
            assert len(tokens) == len(tags)

            sample = DataSample(
                name="ner",
                data={"tokens": tokens, "tags": tags},
                status=SampleStatus.untrained,
            )
            samples.append(sample)

        self.data_storage.insert_samples(samples=samples)

    def get_latency(self, model) -> float:
        self.logger.info("Measuring latency of the UDT instance.")

        start_time = time.time()
        model.predict(
            {self.tkn_cls_vars.source_column: "Checking for latency"}, top_k=1
        )
        latency = time.time() - start_time

        self.logger.info(f"Latency measured: {latency} seconds.")
        return latency
