import multiprocessing as mp
import os
import shutil
import time
from collections import defaultdict
from typing import List

import thirdai
from platform_common.file_handler import expand_s3_buckets_and_directories
from platform_common.ndb.ndbv2_parser import parse_doc
from platform_common.pydantic_models.feedback_logs import ActionType, FeedbackLog
from platform_common.pydantic_models.training import FileInfo, NDBv2Options, TrainConfig
from thirdai import neural_db_v2 as ndbv2
from train_job.models.model import Model
from train_job.reporter import Reporter
from train_job.utils import check_disk, get_directory_size


class NeuralDBV2(Model):
    def __init__(self, config: TrainConfig, reporter: Reporter):
        super().__init__(config=config, reporter=reporter)

        self.logger.info(f"THIRDAI VERSION {thirdai.__version__}")

        self.ndb_options: NDBv2Options = self.config.model_options.ndb_options

        splade = self.ndb_options.advanced_search

        if self.config.base_model_id:
            base_model_path = os.path.join(
                self.config.model_bazaar_dir,
                "models",
                self.config.base_model_id,
                "model.ndb",
            )
            self.logger.info(f"Starting training from base model: {base_model_path}")
            # It seems like this can cause an issue if it runs at the same time as
            # a deployment job starts because the DB files are modified by the deployment
            # job which can cause errors during copying.
            shutil.copytree(
                base_model_path,
                self.ndb_save_path(),
                ignore=shutil.ignore_patterns("*.tmpdb"),
                dirs_exist_ok=True,
            )
            self.db = ndbv2.NeuralDB.load(self.ndb_save_path())
        else:
            self.logger.info("Creating new NDBv2 model")
            if self.ndb_options.on_disk:
                save_path = self.ndb_save_path()
            else:
                save_path = None
            self.db = ndbv2.NeuralDB(save_path=save_path, splade=splade)

    def ndb_save_path(self):
        return os.path.join(self.model_dir, "model.ndb")

    def doc_save_path(self):
        return os.path.join(self.ndb_save_path(), "documents")

    def unsupervised_files(self) -> List[FileInfo]:
        return expand_s3_buckets_and_directories(self.config.data.unsupervised_files)

    def supervised_files(self) -> List[FileInfo]:
        all_files = expand_s3_buckets_and_directories(self.config.data.supervised_files)
        for file in all_files:
            if file.ext() != ".csv" and file.ext() != ".jsonl":
                raise ValueError(
                    "Only CSV or jsonl files are supported for NDB supervised training."
                )
        return all_files

    def unsupervised_train(self, files: List[FileInfo], batch_size=500):
        self.logger.info("Starting unsupervised training.")

        n_jobs = max(1, min(os.cpu_count() - 6, 20))

        self.logger.info(f"Using {n_jobs} parsing jobs")

        doc_save_dir = self.doc_save_path()
        tmp_dir = self.data_dir / "unsupervised"

        docs_indexed = 0

        batches = [files[i : i + batch_size] for i in range(0, len(files), batch_size)]
        with mp.Pool(processes=n_jobs) as pool:
            first_batch_start = time.perf_counter()
            curr_batch = pool.starmap(
                parse_doc,
                [(doc, doc_save_dir, tmp_dir) for doc in batches[0]],
                chunksize=10,
            )
            first_batch_end = time.perf_counter()
            self.logger.info(
                f"Parsed first batch time={first_batch_end - first_batch_start:.3f}s"
            )

            for i in range(len(batches)):
                start = time.perf_counter()
                if i + 1 < len(batches):
                    next_batch = pool.starmap_async(
                        parse_doc,
                        [(doc, doc_save_dir, tmp_dir) for doc in batches[i + 1]],
                        chunksize=10,
                    )
                else:
                    next_batch = None

                index_start = time.perf_counter()
                self.db.insert(curr_batch)
                index_end = time.perf_counter()

                docs_indexed += len(curr_batch)

                if next_batch:
                    next_batch.wait()
                    curr_batch = next_batch.get()

                end = time.perf_counter()
                self.logger.info(
                    f"Inserted batch time={end-start:.3f} insert_time={index_end-index_start:.3f} total_docs={docs_indexed}"
                )

        total_chunks = self.db.retriever.retriever.size()
        self.logger.info(
            f"Completed unsupervised training total_docs={docs_indexed} total_chunks={total_chunks}."
        )

    def rlhf_retraining(self, path: str):
        feedback_samples = defaultdict(int)
        with open(path, "r") as file:
            for line in file:
                feedback = FeedbackLog.model_validate_json(line)
                feedback_samples[feedback.event.action] += 1
                if feedback.event.action == ActionType.upvote:
                    weight = 2  # Extra weighting for explicit upvotes
                    self.db.upvote(
                        queries=feedback.event.queries * weight,
                        chunk_ids=feedback.event.chunk_ids * weight,
                    )
                elif feedback.event.action == ActionType.associate:
                    self.db.associate(
                        sources=feedback.event.sources,
                        targets=feedback.event.targets,
                    )
                elif feedback.event.action == ActionType.implicit_upvote:
                    self.db.upvote(
                        queries=[feedback.event.query],
                        chunk_ids=[feedback.event.chunk_id],
                    )
        sample_counts = " ".join(f"{k}={v}" for k, v in feedback_samples.items())
        self.logger.info(
            "Completed RLHF supervised training. Samples per feedback type: "
            + sample_counts
        )

    def supervised_train(self, files: List[FileInfo]):
        self.logger.info("Starting supervised training.")

        for file in files:
            if file.ext() == ".jsonl":
                self.rlhf_retraining(file.path)
            else:
                supervised_dataset = ndbv2.supervised.CsvSupervised(
                    file.path,
                    query_column=file.options.get("csv_query_column"),
                    id_column=file.options.get("csv_id_column"),
                    id_delimiter=file.options.get("csv_id_delimiter"),
                )

                self.db.supervised_train(supervised_dataset)

                self.logger.info(f"Completed CSV supervised training on {file.path}.")

        self.logger.info("Completed supervised training.")

    def train(self, **kwargs):
        """
        Train the NeuralDB with unsupervised and supervised data.
        """
        self.logger.info("Training process started.")
        self.reporter.report_status(self.config.model_id, "in_progress")

        s = time.perf_counter()
        unsupervised_files = self.unsupervised_files()
        e = time.perf_counter()
        self.logger.info(
            f"Listed {len(unsupervised_files)} unsupervised files in {e-s:.4f} seconds"
        )

        s = time.perf_counter()
        supervised_files = self.supervised_files()
        e = time.perf_counter()
        self.logger.info(
            f"Listed {len(supervised_files)} supervised files in {e-s:.4f} seconds"
        )

        start_time = time.time()

        if unsupervised_files:
            self.logger.info(f"Found {len(unsupervised_files)} unsupervised files.")
            check_disk(self.db, self.config.model_bazaar_dir, unsupervised_files)
            self.unsupervised_train(unsupervised_files)

        if supervised_files:
            self.logger.info(f"Found {len(supervised_files)} supervised files.")
            check_disk(self.db, self.config.model_bazaar_dir, supervised_files)
            self.supervised_train(supervised_files)

        train_time = time.time() - start_time
        self.logger.info(f"Total training time: {train_time} seconds")

        if self.config.data.deletions:
            for doc_id in self.config.data.deletions:
                self.db.delete_doc(doc_id=doc_id)
            self.logger.info(f"Deleted {len(self.config.data.deletions)} docs.")

        self.save()
        self.logger.info("Model saved successfully.")

        self.finalize_training(train_time)
        self.logger.info("Training finalized successfully.")

    def evaluate(self, **kwargs):
        """
        Evaluate the NeuralDB. Not implemented.
        """
        self.logger.warning("Evaluation method called. Not implemented.")

    def save(self):
        if not self.ndb_options.on_disk:
            self.db.save(self.ndb_save_path())

    def get_latency(self) -> float:
        self.logger.info("Measuring latency of the NeuralDBv2 instance.")
        start_time = time.time()

        self.db.search("Checking for latency", top_k=5)

        latency = time.time() - start_time
        self.logger.info(f"Latency measured: {latency} seconds.")
        return latency

    def get_size_in_memory(self) -> int:
        def get_size(path):
            if os.path.isfile(path):
                return os.stat(path).st_size
            return get_directory_size(path)

        # TODO(Nicholas): update this calculation for on_disk=True
        size_in_memory = int(
            get_size(self.db.retriever_path(self.ndb_save_path())) * 1.5
            + get_size(self.db.chunk_store_path(self.ndb_save_path()))
        )
        self.logger.info(f"Size of the model in memory: {size_in_memory} bytes")
        return size_in_memory

    def finalize_training(self, train_time: int):
        self.logger.info("Finalizing training process.")

        self.reporter.report_complete(
            model_id=self.config.model_id,
            metadata={
                "num_params": str(self.db.retriever.retriever.size()),
                "size": str(get_directory_size(self.ndb_save_path())),
                "size_in_memory": str(self.get_size_in_memory()),
                "thirdai_version": str(thirdai.__version__),
                "training_time": str(train_time),
                "latency": str(self.get_latency()),
            },
        )
        self.logger.info("Training finalized and reported successfully.")
