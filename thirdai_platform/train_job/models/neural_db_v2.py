import json
import multiprocessing as mp
import os
import shutil
import time
from collections import defaultdict
from logging import Logger
from typing import List

import thirdai
from llm_cache_job.utils import CacheInsertLog
from platform_common.file_handler import expand_cloud_buckets_and_directories
from platform_common.logging.logcodes import LogCode
from platform_common.ndb.ndbv2_parser import parse_doc
from platform_common.ndb.utils import delete_docs_and_remove_files
from platform_common.pydantic_models.feedback_logs import ActionType, FeedbackLog
from platform_common.pydantic_models.training import FileInfo, TrainConfig
from thirdai import neural_db_v2 as ndbv2
from thirdai.neural_db_v2.chunk_stores import PandasChunkStore
from thirdai.neural_db_v2.retrievers import FinetunableRetriever
from train_job.models.model import Model
from train_job.reporter import Reporter
from train_job.utils import check_disk, get_directory_size


class NeuralDBV2(Model):
    def __init__(self, config: TrainConfig, reporter: Reporter, logger: Logger):
        super().__init__(config=config, reporter=reporter, logger=logger)

        self.on_disk = self.config.model_options.on_disk
        splade = self.config.model_options.advanced_search

        self.logger.info(
            f"NDB options - advanced_search: {splade}, on_disk: {self.on_disk}"
        )

        self.llm_cache = None

        if self.config.base_model_id:
            base_model_path = os.path.join(
                self.config.model_bazaar_dir,
                "models",
                self.config.base_model_id,
                "model.ndb",
            )
            self.logger.info(
                f"Starting training from base model: {base_model_path}",
                code=LogCode.MODEL_INIT,
            )
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

            with open(ndbv2.NeuralDB.metadata_path(self.ndb_save_path()), "r") as f:
                ndb_save_metadata = json.load(f)
            chunk_store_name = ndb_save_metadata["chunk_store_name"]
            if chunk_store_name == "PandasChunkStore":
                self.on_disk = False

            # copy the cache over and load the cache
            cache_path = os.path.join(
                self.config.model_bazaar_dir,
                "models",
                self.config.base_model_id,
                "llm_cache",
            )

            if os.path.exists(cache_path):
                shutil.copytree(
                    cache_path,
                    self.llm_cache_folder_path(),
                    ignore=shutil.ignore_patterns("*.tmpdb"),
                    dirs_exist_ok=True,
                )
                self.llm_cache = ndbv2.NeuralDB.load(self.llm_cache_ndb_path())
        else:
            self.logger.info("Creating new NDBv2 model", code=LogCode.MODEL_INIT)
            if self.on_disk:
                self.db = ndbv2.NeuralDB(save_path=self.ndb_save_path(), splade=splade)
            else:
                # For the in memory model we create the chunk store in memory
                # but the retriever is still on disk. The reason for this is
                # because it's a good tradeoff between construction/inference time
                # and RAM. We'll get most of the speed gains but at around half
                # the RAM usage per model. We could have two flags for
                # on_disk_chunk_store and on_disk_retriever but that would conflict
                # with the existing on disk flag and expose confusing internals to users.
                self.db = ndbv2.NeuralDB(
                    chunk_store=PandasChunkStore(),
                    retriever=FinetunableRetriever(self.retriever_save_path()),
                    splade=splade,
                )

    def retriever_save_path(self):
        return os.path.join(self.model_dir, "train_retriever")

    def ndb_save_path(self):
        return os.path.join(self.model_dir, "model.ndb")

    def llm_cache_ndb_path(self):
        return os.path.join(self.model_dir, "llm_cache", "llm_cache.ndb")

    def llm_cache_folder_path(self):
        return os.path.join(self.model_dir, "llm_cache")

    def doc_save_path(self):
        return os.path.join(self.ndb_save_path(), "documents")

    def unsupervised_files(self) -> List[FileInfo]:
        return expand_cloud_buckets_and_directories(self.config.data.unsupervised_files)

    def supervised_files(self) -> List[FileInfo]:
        all_files = expand_cloud_buckets_and_directories(
            self.config.data.supervised_files
        )
        for file in all_files:
            if file.ext() != ".csv" and file.ext() != ".jsonl":
                raise ValueError(
                    "Only CSV or jsonl files are supported for NDB supervised training."
                )
        return all_files

    def unsupervised_train(self, files: List[FileInfo], batch_size=500):
        self.logger.debug("Starting unsupervised training.")

        n_jobs = max(1, min(os.cpu_count() - 6, 20))

        self.logger.debug(f"Using {n_jobs} parsing jobs")

        doc_save_dir = self.doc_save_path()
        tmp_dir = self.data_dir / "unsupervised"

        docs_indexed = 0
        successfully_indexed_files = 0

        batches = [files[i : i + batch_size] for i in range(0, len(files), batch_size)]
        with mp.Pool(processes=n_jobs) as pool:
            first_batch_start = time.perf_counter()
            curr_batch = pool.starmap(
                parse_doc,
                [(doc, doc_save_dir, tmp_dir) for doc in batches[0]],
                chunksize=10,
            )
            first_batch_end = time.perf_counter()
            self.logger.debug(
                f"First batch parsed in {first_batch_end - first_batch_start:.3f}s"
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

                docs = []
                for doc_idx, doc in enumerate(curr_batch):
                    if not doc:
                        msg = f"Unable to parse {batches[i][doc_idx].path}. Unsupported filetype."
                        self.logger.error(msg, code=LogCode.MODEL_INSERT)
                        self.reporter.report_warning(
                            model_id=self.config.model_id,
                            message=msg,
                        )
                    else:
                        docs.append(doc)

                index_start = time.perf_counter()
                self.db.insert(docs)
                index_end = time.perf_counter()

                docs_indexed += len(curr_batch)
                successfully_indexed_files += len(docs)

                if next_batch:
                    next_batch.wait()
                    curr_batch = next_batch.get()

                end = time.perf_counter()
                self.logger.debug(
                    f"Batch {i+1} inserted in {end - start:.3f}s, insertion time: {index_end - index_start:.3f}s, "
                    f"total documents indexed so far: {docs_indexed}"
                )

        total_chunks = self.db.retriever.retriever.size()
        self.logger.info(
            f"Completed unsupervised training total_docs={docs_indexed} total_chunks={total_chunks}.",
            code=LogCode.MODEL_INSERT,
        )

        upsert_doc_ids = [
            file.source_id
            for file in files
            if file.source_id and file.options.get("upsert", False)
        ]

        self.logger.info(
            f"Found {len(upsert_doc_ids)} docs to upsert, removing old versions",
            code=LogCode.MODEL_DELETE,
        )

        try:
            delete_docs_and_remove_files(
                db=self.db,
                doc_ids=upsert_doc_ids,
                full_documents_path=self.doc_save_path(),
                keep_latest_version=True,
            )
        except Exception as e:
            self.logger.error(
                f"Failed to delete upserted files with error {e}",
                code=LogCode.MODEL_DELETE,
            )

        total_chunks = self.db.retriever.retriever.size()
        self.logger.info(
            f"After removing old doc versions total_chunks={total_chunks}",
            code=LogCode.MODEL_DELETE,
        )

        return successfully_indexed_files

    def rlhf_retraining(self, path: str):
        feedback_samples = defaultdict(int)
        self.logger.info(f"Starting RLHF retraining using file: {path}")
        with open(path, "r") as file:
            for line in file:
                feedback = FeedbackLog.model_validate_json(line)
                if not feedback.perform_rlhf_later:
                    continue

                if feedback.event.action == ActionType.upvote:
                    weight = 2  # Extra weighting for explicit upvotes
                    try:
                        self.db.upvote(
                            queries=feedback.event.queries * weight,
                            chunk_ids=feedback.event.chunk_ids * weight,
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Failed to upvote with error {e}", code=LogCode.MODEL_RLHF
                        )
                        continue
                elif feedback.event.action == ActionType.associate:
                    try:
                        self.db.associate(
                            sources=feedback.event.sources,
                            targets=feedback.event.targets,
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Failed to associate with error {e}",
                            code=LogCode.MODEL_RLHF,
                        )
                        continue
                elif feedback.event.action == ActionType.implicit_upvote:
                    try:
                        self.db.upvote(
                            queries=[feedback.event.query],
                            chunk_ids=[feedback.event.chunk_id],
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Failed to implicit upvote with error {e}",
                            code=LogCode.MODEL_RLHF,
                        )
                        continue

                feedback_samples[feedback.event.action] += 1

        sample_counts = " ".join(f"{k}={v}" for k, v in feedback_samples.items())
        self.logger.info(
            "Completed RLHF supervised training. Samples per feedback type: "
            + sample_counts,
            code=LogCode.MODEL_RLHF,
        )

    def supervised_train(self, files: List[FileInfo]):
        self.logger.info("Starting supervised training.", code=LogCode.MODEL_RLHF)

        successfully_trained_files = 0

        for file in files:
            if file.ext() == ".jsonl":
                try:
                    self.rlhf_retraining(file.path)
                    successfully_trained_files += 1
                except Exception as e:
                    msg = f"Failed to train on file {file.path} with error {e}"
                    self.logger.error(msg, code=LogCode.MODEL_RLHF)
                    self.reporter.report_warning(
                        model_id=self.config.model_id,
                        message=msg,
                    )
            else:
                try:
                    supervised_dataset = ndbv2.supervised.CsvSupervised(
                        file.path,
                        query_column=file.options.get("csv_query_column"),
                        id_column=file.options.get("csv_id_column"),
                        id_delimiter=file.options.get("csv_id_delimiter"),
                    )

                    self.db.supervised_train(supervised_dataset)

                    self.logger.info(
                        f"Completed CSV supervised training on {file.path}.",
                        code=LogCode.MODEL_RLHF,
                    )
                    successfully_trained_files += 1
                except Exception as e:
                    msg = f"Failed to train on file {file.path} with error {e}"
                    self.logger.error(msg, code=LogCode.MODEL_RLHF)
                    self.reporter.report_warning(
                        model_id=self.config.model_id,
                        message=msg,
                    )

        self.logger.info("Completed supervised training.", code=LogCode.MODEL_RLHF)

        return successfully_trained_files

    def train(self, **kwargs):
        """
        Train the NeuralDB with unsupervised and supervised data.
        """
        self.logger.info("Training process started.", code=LogCode.MODEL_TRAIN)
        self.reporter.report_status(self.config.model_id, "in_progress")

        s = time.perf_counter()
        unsupervised_files = self.unsupervised_files()
        e = time.perf_counter()
        self.logger.debug(
            f"Listed {len(unsupervised_files)} unsupervised files in {e-s:.4f} seconds"
        )

        s = time.perf_counter()
        supervised_files = self.supervised_files()
        e = time.perf_counter()
        self.logger.debug(
            f"Listed {len(supervised_files)} supervised files in {e-s:.4f} seconds"
        )

        start_time = time.time()

        successfully_indexed_files = 0
        if unsupervised_files:
            check_disk(self.db, self.config.model_bazaar_dir, unsupervised_files)
            successfully_indexed_files = self.unsupervised_train(unsupervised_files)

        successfully_trained_files = 0
        if supervised_files:
            check_disk(self.db, self.config.model_bazaar_dir, supervised_files)
            successfully_trained_files = self.supervised_train(supervised_files)

        if len(unsupervised_files) > 0 or len(supervised_files) > 0:
            if successfully_indexed_files == 0 and successfully_trained_files == 0:
                msg = "The number of documents indexed and trained is 0. Marking training as failed."
                self.logger.error(msg, code=LogCode.MODEL_TRAIN)
                raise ValueError(msg)

        train_time = time.time() - start_time
        self.logger.debug(f"Total training time: {train_time} seconds")

        if self.config.data.deletions:
            delete_docs_and_remove_files(
                db=self.db,
                doc_ids=self.config.data.deletions,
                full_documents_path=self.doc_save_path(),
                keep_latest_version=False,
            )
            self.logger.debug(f"Deleted {len(self.config.data.deletions)} docs.")

        self.save()
        self.logger.info("Model saved successfully.", code=LogCode.MODEL_SAVE)

        if self.llm_cache:
            num_evictions = self.evict_stale_cache_responses()
            self.logger.info(
                f"Evicted {num_evictions} stale responses from llm cache.",
                code=LogCode.LLM_CACHE,
            )

        self.finalize_training(train_time)
        self.logger.info(
            "Training finalized and reported successfully.", code=LogCode.MODEL_TRAIN
        )

    def evict_stale_cache_responses(self, **kwargs) -> int:
        """
        If references used for generation of llm cache responses have changed for
        the same query, delete that response from the cache.
        """
        past_insertions_file = os.path.join(
            self.llm_cache_folder_path(),
            "insertions",
            "past_insertions.jsonl",
        )

        chunk_ids_to_delete = []
        evicted_response_lines = []
        with open(past_insertions_file, "r") as f:
            # TODO (david) Revisit this by adding a chunk iterator in NeuralDB
            # The issue:
            # Determining chunk_id in this way is a bit of a leaky abstraction but
            # since we know NeuralDB assigns chunks in increasing order and we
            # inserted all of the entries in past_insertions.jsonl in order, we
            # can be sure that we're deleting the right ids here. This will be
            # inefficient on subsequent calls since we might loop through ids
            # that have already been deleted, but NeuralDB at least doesn't throw
            # when deleting duplicate ids so this code should be correct.
            for chunk_id, line in enumerate(f.readlines(), start=1):
                log = CacheInsertLog.model_validate_json(line)
                query = log.query
                cache_ref_ids = log.reference_ids
                results = self.db.search(query)
                model_ref_ids = [r[0].chunk_id for r in results][: len(cache_ref_ids)]
                if set(cache_ref_ids) != set(model_ref_ids):
                    chunk_ids_to_delete.append(chunk_id)
                    evicted_response_lines.append(line)

        self.llm_cache.delete(chunk_ids_to_delete)

        evicted_responses_file = os.path.join(
            self.llm_cache_folder_path(),
            "insertions",
            "evicted_responses.jsonl",
        )

        with open(evicted_responses_file, "a") as f:
            for evicted_response_line in evicted_response_lines:
                f.write(evicted_response_line)

        return len(chunk_ids_to_delete)

    def evaluate(self, **kwargs):
        """
        Evaluate the NeuralDB. Not implemented.
        """
        self.logger.warning(
            "Evaluation method called. Not implemented.", code=LogCode.MODEL_EVAL
        )

    def save(self):
        try:
            # If its on disk it should already be saved
            if not self.on_disk:
                # if we're retraining from a base model we need to save the in memory chunk_store
                if self.config.base_model_id:
                    os.remove(self.db.chunk_store_path(self.ndb_save_path()))
                    self.db.chunk_store.save(
                        self.db.chunk_store_path(self.ndb_save_path())
                    )
                else:
                    self.db.save(self.ndb_save_path())
                    # TODO(david/kartik) Find out why this fails this fails only sometimes
                    # Its not essential to the platform to remove it so we don't raise
                    # the exception but it saves disk usage.
                    try:
                        shutil.rmtree(self.retriever_save_path())
                    except Exception as e:
                        self.logger.warning(
                            f"Could not delete retriever with error {e}. Continuing without deleting temp retriever.",
                            code=LogCode.MODEL_SAVE,
                        )

                self.logger.info(
                    f"Model saved to {self.ndb_save_path()}", code=LogCode.MODEL_SAVE
                )
        except Exception as e:
            self.logger.error(
                f"Failed to save model with error {e}", code=LogCode.MODEL_SAVE
            )
            raise e

    def get_latency(self) -> float:
        self.logger.debug("Measuring latency of the NeuralDBv2 instance.")
        start_time = time.time()

        self.db.search("Checking for latency", top_k=5)

        latency = time.time() - start_time
        self.logger.info(
            f"Latency measured: {latency} seconds.", code=LogCode.MODEL_INFO
        )
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
        self.logger.info(
            f"Size of the model in memory: {size_in_memory} bytes",
            code=LogCode.MODEL_INFO,
        )
        return size_in_memory

    def finalize_training(self, train_time: int):
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
