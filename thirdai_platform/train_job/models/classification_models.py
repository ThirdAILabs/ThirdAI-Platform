import json
import math
import os
import random
import shutil
import tempfile
import time
import typing
from abc import abstractmethod
from collections import defaultdict
from datetime import datetime, timezone
from logging import Logger
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import thirdai
from platform_common.file_handler import (
    expand_cloud_buckets_and_directories,
    get_local_file_infos,
)
from platform_common.pii.udt_common_patterns import find_common_pattern
from platform_common.pydantic_models.pii_models import (
    ModelMetrics,
    PerTagMetrics,
    Throughput,
)
from platform_common.pydantic_models.training import (
    TextClassificationOptions,
    TokenClassificationOptions,
    TrainConfig,
    UDTTrainOptions,
)
from platform_common.thirdai_storage.data_types import (
    DataSample,
    LabelEntity,
    LabelStatus,
    Metadata,
    MetadataStatus,
    SampleStatus,
    TagMetadata,
)
from platform_common.thirdai_storage.storage import DataStorage, SQLiteConnector
from thirdai import bolt
from train_job.models.model import Model
from train_job.reporter import Reporter
from train_job.utils import check_csv_only


def get_split_filename(original_name: str, split: str) -> str:
    path, ext = os.path.splitext(original_name)
    return f"{path}_{split}{ext}"


class ClassificationModel(Model):
    report_failure_method = "report_status"

    @property
    def model_save_path(self) -> Path:
        return self.model_dir / "model.udt"

    @property
    def train_options(self) -> UDTTrainOptions:
        return self.config.model_options.train_options

    def train_test_files(self) -> Tuple[List[str], List[str]]:
        train_files = expand_cloud_buckets_and_directories(
            self.config.data.supervised_files
        )
        check_csv_only(train_files)
        self.temp_train_dir = tempfile.mkdtemp()
        train_files = get_local_file_infos(train_files, self.temp_train_dir)
        train_files = [file.path for file in train_files]

        self.logger.info(f"Found {len(train_files)} train files")

        test_files = expand_cloud_buckets_and_directories(self.config.data.test_files)
        check_csv_only(test_files)
        self.temp_test_dir = tempfile.mkdtemp()
        test_files = get_local_file_infos(test_files, self.temp_test_dir)
        test_files = [file.path for file in test_files]

        self.logger.info(f"Found {len(test_files)} test files")

        test_split = self.train_options.test_split
        if len(test_files) == 0 and test_split and test_split > 0:
            self.logger.info(
                f"Test split {test_split} specified, splitting train files into train and test"
            )
            new_train_files = []
            new_test_files = []
            for file in train_files:
                self.logger.info(f"Splitting {file} into train/test")
                df = pd.read_csv(file)
                test = df.sample(frac=test_split)
                train = df.drop(test.index)

                train_split_path = get_split_filename(file, "train")
                test_split_path = get_split_filename(file, "test")
                train.to_csv(train_split_path, index=False)
                test.to_csv(test_split_path, index=False)

                self.logger.info(
                    f"Created {train_split_path} with {len(train)} rows and {test_split_path} with {len(test)} rows"
                )

                new_train_files.append(train_split_path)
                new_test_files.append(test_split_path)

            return new_train_files, new_test_files

        return train_files, test_files

    @abstractmethod
    def initialize_model(self):
        pass

    def cleanup_temp_dirs(self):
        """
        Clean up temporary directories created for downloaded files.
        """
        if hasattr(self, "temp_train_dir") and os.path.isdir(self.temp_train_dir):
            shutil.rmtree(self.temp_train_dir)
            self.logger.info(
                f"Cleaned up supervised files temporary directory: {self.temp_train_dir}"
            )
            del self.temp_train_dir  # Remove attribute after cleanup

        if hasattr(self, "temp_test_dir") and os.path.isdir(self.temp_test_dir):
            shutil.rmtree(self.temp_test_dir)
            self.logger.info(
                f"Cleaned up test files temporary directory: {self.temp_test_dir}"
            )
            del self.temp_test_dir  # Remove attribute after cleanup

    def get_size(self):
        """
        Calculate the size of the model in bytes
        """
        model_size = self.model_save_path.stat().st_size
        self.logger.info(f"Model size on disk: {model_size} bytes.")
        return model_size

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
        udt_path = (
            Path(self.config.model_bazaar_dir) / "models" / model_id / "model.udt"
        )
        self.logger.info(f"UDT path for model {model_id}: {udt_path}")
        return udt_path

    def load_model(self, model_id):
        return bolt.UniversalDeepTransformer.load(str(self.get_udt_path(model_id)))

    def save_model(self, model):
        self.logger.info(f"Saving model to {self.model_save_path}")
        model.save(str(self.model_save_path))

    def get_model(self):
        # if a model with the same id has already been initialized, return the model
        if os.path.exists(self.model_save_path):
            self.logger.info(
                f"Loading existing udt model from save path : {self.model_save_path}"
            )
            return bolt.UniversalDeepTransformer.load(str(self.model_save_path))

        # if model with the id not found but has a base model, return the base model
        if self.config.base_model_id:
            self.logger.info(
                f"Loading base model with model_id: {self.config.base_model_id}"
            )
            return self.load_model(self.config.base_model_id)

        # initialize the model from scratch if the model does not exist or if there is not base model
        self.logger.info("Initializing a new model from scratch.")
        return self.initialize_model()

    def evaluate(self, model, test_files: List[str]):
        self.logger.info("Starting evaluation on test files.")
        for test_file in test_files:
            self.logger.info(f"Evaluating on test file: {test_file}")
            model.evaluate(test_file, metrics=self.train_options.validation_metrics)
        self.logger.info("Evaluation completed.")

    @abstractmethod
    def train(self, **kwargs):
        pass


class TextClassificationModel(ClassificationModel):
    @property
    def txt_cls_vars(self) -> TextClassificationOptions:
        return self.config.model_options.udt_options

    def initialize_model(self):
        self.logger.info("Initializing a new Text Classification model.")
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
        try:
            self.reporter.report_status(self.config.model_id, "in_progress")

            model = self.get_model()

            train_files, test_files = self.train_test_files()

            start_time = time.time()
            for train_file in train_files:
                self.logger.info(f"Training on supervised file: {train_file}")
                model.train(
                    train_file,
                    epochs=self.train_options.supervised_epochs,
                    learning_rate=self.train_options.learning_rate,
                    batch_size=self.train_options.batch_size,
                    metrics=self.train_options.metrics,
                )
            training_time = time.time() - start_time
            self.logger.info(f"Training completed in {training_time:.2f} seconds.")

            self.save_model(model)

            self.evaluate(model, test_files)

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
        finally:
            # Ensure cleanup of temporary directories after training, even on failure
            self.cleanup_temp_dirs()

    def get_latency(self, model) -> float:
        self.logger.info("Measuring latency of the UDT instance.")

        start_time = time.time()
        model.predict({self.txt_cls_vars.text_column: "Checking for latency"}, top_k=1)
        latency = time.time() - start_time

        self.logger.info(f"Latency measured: {latency} seconds.")
        return latency


class TokenClassificationModel(ClassificationModel):
    def __init__(self, config: TrainConfig, reporter: Reporter, logger: Logger):
        super().__init__(config, reporter, logger)
        self.load_storage()
        self._num_balancing_samples = 10_000
        self._balancing_samples_path = self.data_dir / "balancing_samples.csv"

    @property
    def tkn_cls_vars(self) -> TokenClassificationOptions:
        return self.config.model_options.udt_options

    def save_model_and_metadata(
        self, model, old_metadata: TagMetadata, latest_metadata: TagMetadata
    ):
        # if both model and db are saved successfully -> consistent state
        # if either fails -> rollback to last state to maintain consistency
        # hotswaping the model reduces the chances of model being in an inconsistent state
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_model_path = Path(temp_dir) / "model.udt"
                model.save(str(temp_model_path))
                self.logger.debug(f"Model saved temporarily at {temp_model_path}")

                self.update_tag_metadata(latest_metadata, MetadataStatus.unchanged)
                self.logger.debug("Metadata updated to latest state")

                shutil.move(temp_model_path, self.model_save_path)
                self.logger.debug(
                    f"Model moved to final destination at {self.model_save_path}"
                )

        except Exception as e:
            self.logger.error(f"Failed to save model and metadata with error {e}")
            self.update_tag_metadata(old_metadata, MetadataStatus.unchanged)
            raise e

    def initialize_model(self):
        self.logger.info("Initializing a new Token Classification model.")
        # remove duplicates from target_labels
        target_labels = list(set(self.tkn_cls_vars.target_labels))
        self.logger.info(f"Target labels: {target_labels}")

        # insert the tags into the storage to keep track of their training status
        tag_status = {
            self.tkn_cls_vars.default_tag: LabelEntity(
                name=self.tkn_cls_vars.default_tag, status=LabelStatus.untrained
            )
        }

        try:
            new_tags = self.config.datagen_options.datagen_options.tags
            for tag in new_tags:
                tag.status = LabelStatus.untrained
                tag_status[tag.name] = tag
        except Exception as e:
            self.logger.warning(f"Failed to load tags from config: {e}, using defaults")
            for label in target_labels:
                tag_status[label] = LabelEntity(
                    name=label,
                    status=LabelStatus.untrained,
                )

        self.update_tag_metadata(
            tag_metadata=TagMetadata(tag_status=tag_status),
            status=MetadataStatus.unchanged,
        )

        default_tag = self.tkn_cls_vars.default_tag

        rule_based_tags = []
        bolt_tags = []
        for tag in target_labels:
            common_pattern = find_common_pattern(tag)
            if common_pattern:
                rule_based_tags.append(common_pattern)
            else:
                bolt_tags.append(tag)

        self.logger.info(f"Rule-based tags: {rule_based_tags}")
        self.logger.info(f"Bolt-based tags: {bolt_tags}")

        model = bolt.UniversalDeepTransformer(
            data_types={
                self.tkn_cls_vars.source_column: bolt.types.text(),
                self.tkn_cls_vars.target_column: bolt.types.token_tags(
                    tags=bolt_tags,
                    default_tag=default_tag,
                ),
            },
            target=self.tkn_cls_vars.target_column,
        )

        for tag in rule_based_tags:
            try:
                model.add_ner_rule(tag)
                self.logger.info(f"Added rule-based tag: {tag}")
            except Exception as e:
                self.logger.error(f"Failed to add rule based tag {tag} with error {e}")

        return model

    def load_storage(self):
        data_storage_path = self.data_dir / "data_storage.db"
        self.logger.info(f"Loading data storage from {data_storage_path}.")
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

    def verify_file(self, model: bolt.UniversalDeepTransformer, file: str):
        source_column, target_column = model.source_target_columns()

        try:
            df = pd.read_csv(file)
        except Exception:
            raise ValueError(
                f"Unable to load csv file {file}. Please ensure that it is a valid csv"
            )

        if source_column not in df.columns or target_column not in df.columns:
            raise ValueError(
                f"Expected csv to have columns '{source_column}' and '{target_column}'"
            )

        new_target = []

        tags = set(model.list_ner_tags())
        extra_tags = set()
        for i, (source, target) in enumerate(zip(df[source_column], df[target_column])):
            if not isinstance(source, str):
                raise ValueError(
                    f"Invalid training data: column '{source_column}' in row {i} of '{file}' cannot be parsed as string."
                )
            if not isinstance(target, str):
                raise ValueError(
                    f"Invalid training data: column '{target_column}' in row {i} of '{file}' cannot be parsed as string."
                )
            source_toks = source.split()
            target_toks = target.split()

            if len(source_toks) != len(target_toks):
                raise ValueError(
                    f"Invalid training data: expected row {i} of '{file}' to have the same number of tokens in source and target columns."
                )

            corrected = []
            for tag in target_toks:
                if tag in tags:
                    corrected.append(tag)
                else:
                    extra_tags.add(tag)
                    corrected.append("O")
            new_target.append(" ".join(corrected))

        if extra_tags:
            for tag in extra_tags:
                msg = f"Found unexpected entity tag '{tag}' in dataset. Instances of this tag will treated as untagged. Expected tags are {', '.join(tags)}"
                self.logger.warning(msg)
                self.reporter.report_warning(self.config.model_id, msg)
            df[target_column] = new_target
            df.to_csv(file, index=False)

    def train(self, **kwargs):
        try:
            self.reporter.report_status(self.config.model_id, "in_progress")

            model = self.get_model()

            train_files, test_files = self.train_test_files()

            for file in train_files + test_files:
                self.verify_file(model, file)

            before_train_metrics = ModelMetrics(
                per_tag_metrics=(
                    None
                    if len(test_files) == 0
                    else self.per_tag_metrics(
                        model=model,
                        test_files=test_files,
                        samples_to_collect=0,
                    )
                ),
                throughput=self.measure_throughput(model, train_files + test_files),
            )

            start_time = time.time()

            source_column, target_column = model.source_target_columns()

            balancing_samples_path = self.find_and_save_balancing_samples()

            # insert samples into data storage for later use
            self.insert_samples_in_storage(
                train_files, source_column=source_column, target_column=target_column
            )

            tags = self.tag_metadata

            # new labels to add to the model
            new_labels = [
                name
                for name, label in tags.tag_status.items()
                if label.status == LabelStatus.uninserted
            ]
            self.logger.info(f"New labels to add: {new_labels}")

            for new_label in new_labels:
                common_pattern = find_common_pattern(new_label)
                try:
                    if common_pattern:
                        self.logger.debug(
                            f"Adding rule based tag {common_pattern} to the model."
                        )
                        model.add_ner_rule(common_pattern)
                    else:
                        self.logger.debug(
                            f"Adding bolt based tag {new_label} to the model."
                        )
                        model.add_ner_entities([new_label])
                except Exception as e:
                    self.logger.error(
                        f"Failed to add new label {new_label} to the model with error {e}."
                    )

            for train_file in train_files:
                self.logger.info(f"Training on file: {train_file}")
                model.train(
                    train_file,
                    epochs=self.train_options.supervised_epochs,
                    learning_rate=self.train_options.learning_rate,
                    batch_size=self.train_options.batch_size,
                    metrics=self.train_options.metrics,
                )

            if balancing_samples_path:
                self.logger.info(
                    f"Training on balancing samples from {balancing_samples_path}."
                )
                model.train(
                    str(balancing_samples_path),
                    epochs=1,
                    learning_rate=self.train_options.learning_rate,
                    batch_size=self.train_options.batch_size,
                    metrics=self.train_options.metrics,
                )

            training_time = time.time() - start_time
            self.logger.info(f"Training completed in {training_time:.2f} seconds.")

            after_train_metrics = ModelMetrics(
                per_tag_metrics=(
                    None
                    if len(test_files) == 0
                    else self.per_tag_metrics(
                        model=model,
                        test_files=test_files,
                        samples_to_collect=5,
                    )
                ),
                throughput=self.measure_throughput(model, train_files + test_files),
            )

            self.save_train_report(
                before_train_metrics=before_train_metrics,
                after_train_metrics=after_train_metrics,
            )

            # converts the status of all tags to trained and update in the storage
            for tag in tags.tag_status:
                tags.tag_status[tag].status = LabelStatus.trained

            # this is atomic in the sense that if model and db are in a consistent state if anything fails
            self.save_model_and_metadata(
                model,
                old_metadata=self.tag_metadata,  # db still holds old metadata
                latest_metadata=tags,
            )

            self.data_storage.update_sample_status("ner", SampleStatus.trained)

            self.evaluate(model, test_files)

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
        finally:
            # Ensure cleanup of temporary directories after training, even on failure
            self.cleanup_temp_dirs()

    def measure_throughput(self, model, files: List[str]):
        source_col, _ = model.source_target_columns()

        number_samples_for_throughput_measurement = 2000
        samples = []
        for file in files:
            df = pd.read_csv(file)
            for row in df.itertuples():
                if len(samples) < number_samples_for_throughput_measurement:
                    samples.append({source_col: getattr(row, source_col)})

        if len(samples) > 500:
            # to get any meaningful throughput measurements we need to run inference on a
            # sufficiently large number of samples
            batch_inference_start_time = time.time()
            model.predict(samples, top_k=1)
            batch_inference_time = max(time.time() - batch_inference_start_time, 1e-6)
            self.logger.info(
                f"Batch inference time: {batch_inference_time:.2f} seconds."
            )

            number_tokens = 0
            for sample in samples:
                number_tokens += len(sample[source_col].split())

            token_throughput = number_tokens / batch_inference_time
            sample_throughput = len(samples) / batch_inference_time
            self.logger.info(
                f"Token throughput: {token_throughput:.2f} tokens per second."
            )
            self.logger.info(
                f"Sample throughput: {sample_throughput:.2f} samples per second."
            )

            return Throughput(
                token_throughput=token_throughput,
                sample_throughput=sample_throughput,
            )

        self.logger.warning(
            "Not enough samples to measure throughput. Skipping throughput measurement."
        )
        return Throughput(token_throughput=None, sample_throughput=None)

    def per_tag_metrics(
        self,
        model,
        test_files: List[str],
        samples_to_collect: int,
    ):
        true_positives = defaultdict(int)
        false_positives = defaultdict(int)
        false_negatives = defaultdict(int)

        true_positive_samples = defaultdict(list)
        false_positive_samples = defaultdict(list)
        false_negative_samples = defaultdict(list)

        source_col, target_col = model.source_target_columns()

        for file in test_files:
            df = pd.read_csv(file)
            for row in df.itertuples():
                source = getattr(row, source_col)
                target = getattr(row, target_col)

                preds = model.predict({source_col: source}, top_k=1)

                predictions = " ".join(p[0][0] for p in preds)
                labels = target.split()
                for i, (pred, label) in enumerate(zip(preds, labels)):
                    tag = pred[0][0]
                    if tag == label:
                        true_positives[label] += 1
                        if len(true_positive_samples[label]) < samples_to_collect:
                            true_positive_samples[label].append(
                                {
                                    "source": source,
                                    "target": target,
                                    "predictions": predictions,
                                    "index": i,
                                }
                            )
                    else:
                        false_positives[tag] += 1
                        if len(false_positive_samples[tag]) < samples_to_collect:
                            false_positive_samples[tag].append(
                                {
                                    "source": source,
                                    "target": target,
                                    "predictions": predictions,
                                    "index": i,
                                }
                            )
                        false_negatives[label] += 1
                        if len(false_negative_samples[label]) < samples_to_collect:
                            false_negative_samples[label].append(
                                {
                                    "source": source,
                                    "target": target,
                                    "predictions": predictions,
                                    "index": i,
                                }
                            )

        metric_summary = {}
        for tag in model.list_ner_tags():
            if tag == "O":
                continue

            tp = true_positives[tag]

            if tp + false_positives[tag] == 0:
                precision = float("nan")
            else:
                precision = tp / (tp + false_positives[tag])

            if tp + false_negatives[tag] == 0:
                recall = float("nan")
            else:
                recall = tp / (tp + false_negatives[tag])

            if precision + recall == 0:
                fmeasure = float("nan")
            else:
                fmeasure = 2 * precision * recall / (precision + recall)

            metric_summary[tag] = {
                "precision": "NaN" if math.isnan(precision) else round(precision, 3),
                "recall": "NaN" if math.isnan(recall) else round(recall, 3),
                "fmeasure": "NaN" if math.isnan(fmeasure) else round(fmeasure, 3),
            }

        def remove_null_tag(samples: Dict[str, Any]) -> Dict[str, Any]:
            return {k: v for k, v in samples.items() if k != "O"}

        return PerTagMetrics(
            metrics=metric_summary,
            true_positives=remove_null_tag(true_positive_samples),
            false_positives=remove_null_tag(false_positive_samples),
            false_negatives=remove_null_tag(false_negative_samples),
        )

    def save_train_report(
        self, before_train_metrics: ModelMetrics, after_train_metrics: ModelMetrics
    ):
        train_report = {
            "before_train_metrics": before_train_metrics.model_dump_json(),
            "after_train_metrics": after_train_metrics.model_dump_json(),
        }

        timestamp = int(datetime.now(timezone.utc).timestamp())
        report_path = self.model_dir / "train_reports" / f"{timestamp}.json"
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w") as file:
            json.dump(train_report, file, indent=4)

    def insert_samples_in_storage(
        self,
        supervised_files: typing.List[str],
        source_column: str,
        target_column: str,
    ):
        # these samples will be used as balancing samples for the training of the model
        # this sampling is not uniform but we assume that there won't be many samples
        # TODO(Shubh) : make this sampling uniform using reservoir sampling
        self.logger.info("Inserting samples into data storage for training.")
        df = pd.DataFrame()
        for supervised_file in supervised_files:
            self.logger.info(f"Loading data from {supervised_file}")
            new_df = pd.read_csv(supervised_file)
            new_df = new_df[[source_column, target_column]]

            df = pd.concat([df, new_df])

        samples = []

        for row in df.itertuples():
            tokens = getattr(row, source_column).split()
            tags = getattr(row, target_column).split()
            assert len(tokens) == len(
                tags
            ), f"length of source tokens ≠ length of target tokens."

            sample = DataSample(
                name="ner",
                data={"tokens": tokens, "tags": tags},
                status=SampleStatus.untrained,
            )
            samples.append(sample)

        self.logger.info(f"Inserting {len(samples)} samples into storage.")

        self.data_storage.insert_samples(samples=samples)
        num_samples_in_storage = self.data_storage.connector.get_sample_count("ner")

        self.logger.info(
            f"Number of samples in storage after insertion: {num_samples_in_storage}"
        )

    def find_and_save_balancing_samples(self):
        self.logger.info("Finding balancing samples for training.")
        user_provided_samples = self.data_storage.retrieve_samples(
            name="ner", num_samples=None, user_provided=True
        )
        non_user_provided_samples = self.data_storage.retrieve_samples(
            name="ner", num_samples=None, user_provided=False
        )

        samples = []

        self.logger.info(f"Found {len(user_provided_samples)} user provided samples.")
        for user_provided_sample in user_provided_samples:
            samples.append(
                {
                    self.tkn_cls_vars.source_column: " ".join(
                        user_provided_sample.data.tokens
                    ),
                    self.tkn_cls_vars.target_column: " ".join(
                        user_provided_sample.data.tags
                    ),
                    "user_provided": True,
                }
            )

        self.logger.info(
            f"Found {len(non_user_provided_samples)} non user provided samples. Adding {min(self._num_balancing_samples, len(non_user_provided_samples))} samples to the balancing set."
        )
        random.shuffle(non_user_provided_samples)

        for sample in non_user_provided_samples[: self._num_balancing_samples]:
            samples.append(
                {
                    self.tkn_cls_vars.source_column: " ".join(sample.data.tokens),
                    self.tkn_cls_vars.target_column: " ".join(sample.data.tags),
                    "user_provided": False,
                }
            )

        if len(samples) > 0:
            self.logger.info(
                f"Saving balancing samples to {self._balancing_samples_path}"
            )
            dataframe = pd.DataFrame(samples)
            dataframe.to_csv(self._balancing_samples_path, index=False)
            return self._balancing_samples_path

        return None

    def get_latency(self, model) -> float:
        self.logger.info("Measuring latency of the Token Classification model.")

        start_time = time.time()
        model.predict(
            {model.source_target_columns()[0]: "Checking for latency"}, top_k=1
        )
        latency = time.time() - start_time

        self.logger.info(f"Latency measured: {latency} seconds.")
        return latency
