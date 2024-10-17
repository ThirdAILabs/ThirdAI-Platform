import time
from abc import abstractmethod
from pathlib import Path
from typing import List

import thirdai
from platform_common.file_handler import expand_cloud_buckets_and_directories
from platform_common.pydantic_models.training import (
    FileInfo,
    TextClassificationOptions,
    TokenClassificationOptions,
    UDTTrainOptions,
)
from thirdai import bolt
from train_job.exceptional_handler import apply_exception_handler
from train_job.models.model import Model
from train_job.utils import check_csv_only, check_local_nfs_only


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
        all_files = expand_cloud_buckets_and_directories(
            self.config.data.supervised_files
        )
        check_csv_only(all_files)
        check_local_nfs_only(all_files)
        return all_files

    def test_files(self) -> List[FileInfo]:
        all_files = expand_cloud_buckets_and_directories(self.config.data.test_files)
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
        return bolt.UniversalDeepTransformer.load(self.get_udt_path(model_id))

    def save_model(self, model):
        model.save(str(self.model_save_path))

    def get_model(self):
        if self.config.base_model_id:
            return self.load_model(self.config.base_model_id)
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
    @property
    def tkn_cls_vars(self) -> TokenClassificationOptions:
        return self.config.model_options.udt_options

    def initialize_model(self):
        # deduplicate the labels
        target_labels = list(set(self.tkn_cls_vars.target_labels))
        default_tag = self.tkn_cls_vars.default_tag
        return bolt.UniversalDeepTransformer(
            data_types={
                self.tkn_cls_vars.source_column: bolt.types.text(),
                self.tkn_cls_vars.target_column: bolt.types.token_tags(
                    tags=target_labels, default_tag=default_tag
                ),
            },
            target=self.tkn_cls_vars.target_column,
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
        model.predict(
            {self.tkn_cls_vars.source_column: "Checking for latency"}, top_k=1
        )
        latency = time.time() - start_time

        self.logger.info(f"Latency measured: {latency} seconds.")
        return latency
