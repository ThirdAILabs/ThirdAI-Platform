import json
import multiprocessing as mp
import os
import shutil
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import thirdai
from config import FileInfo, NDBv2Options, TrainConfig
from fastapi import Response
from feedback_logs import ActionType, FeedbackLog
from models.model import Model
from reporter import Reporter
from thirdai import neural_db_v2 as ndbv2
from utils import (
    check_disk,
    create_s3_client,
    expand_s3_buckets_and_directories,
    get_directory_size,
)


def convert_to_ndb_doc(
    resource_path: str,
    display_path: str,
    doc_id: Optional[str],
    metadata: Optional[Dict[str, Any]],
    options: Dict[str, Any],
) -> ndbv2.Document:
    filename, ext = os.path.splitext(resource_path)

    if ext == ".pdf":
        return ndbv2.PDF(
            resource_path,
            doc_metadata=metadata,
            display_path=display_path,
            doc_id=doc_id,
        )
    elif ext == ".docx":
        return ndbv2.DOCX(
            resource_path,
            doc_metadata=metadata,
            display_path=display_path,
            doc_id=doc_id,
        )
    elif ext == ".html":
        with open(resource_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        dummy_response = Response()
        dummy_response.status_code = 200
        dummy_response._content = html_content.encode("utf-8")

        return ndbv2.URL(
            os.path.basename(filename),
            response=dummy_response,
            doc_metadata=metadata,
            doc_id=doc_id,
        )
    elif ext == ".csv":
        return ndbv2.CSV(
            resource_path,
            keyword_columns=options.get("csv_strong_columns", []),
            text_columns=options.get("csv_weak_columns", []),
            doc_metadata=metadata,
            display_path=display_path,
            doc_id=doc_id,
        )
    else:
        raise TypeError(f"{ext} Document type isn't supported yet.")


def preload_chunks(
    resource_path: str,
    display_path: str,
    doc_id: Optional[str],
    metadata: Optional[Dict[str, Any]],
    options: Dict[str, Any],
) -> Tuple[ndbv2.Document, str]:
    doc = convert_to_ndb_doc(
        resource_path=resource_path,
        display_path=display_path,
        doc_id=doc_id,
        metadata=metadata,
        options=options,
    )
    return ndbv2.documents.PrebatchedDoc(list(doc.chunks()), doc_id=doc.doc_id())


def parse_doc(
    doc: FileInfo, doc_save_dir: str, tmp_dir: str
) -> Tuple[ndbv2.Document, str]:
    """
    Process a file, downloading it from S3 if necessary, and convert it to an NDB file.
    """
    if doc.path.startswith("s3://"):
        try:
            s3_client = create_s3_client()
            bucket_name, prefix = doc.path.replace("s3://", "").split("/", 1)
            local_file_path = os.path.join(tmp_dir, os.path.basename(prefix))

            s3_client.download_file(bucket_name, prefix, local_file_path)
        except Exception as error:
            print(f"Error downloading file '{doc.path}' from s3 : {error}")
            raise ValueError(f"Error downloading file '{doc.path}' from s3 : {error}")

        ndb_doc = preload_chunks(
            resource_path=local_file_path,
            display_path=f"/{bucket_name}.s3.amazonaws.com/{prefix}",
            doc_id=doc.doc_id,
            metadata=doc.metadata,
            options=doc.options,
        )

        os.remove(local_file_path)
        return ndb_doc

    save_artifact_uuid = str(uuid.uuid4())
    artifact_dir = os.path.join(doc_save_dir, save_artifact_uuid)
    os.makedirs(artifact_dir, exist_ok=True)
    shutil.copy(src=doc.path, dst=artifact_dir)

    return preload_chunks(
        resource_path=os.path.join(artifact_dir, os.path.basename(doc.path)),
        display_path=os.path.join(save_artifact_uuid, os.path.basename(doc.path)),
        doc_id=doc.doc_id,
        metadata=doc.metadata,
        options=doc.options,
    )


class NeuralDBV2(Model):
    def __init__(self, config: TrainConfig, reporter: Reporter):
        super().__init__(config=config, reporter=reporter)

        self.logger.info(f"THIRDAI VERSION {thirdai.__version__}")

        self.ndb_options: NDBv2Options = self.config.model_options.ndb_options

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
            self.db = ndbv2.NeuralDB(save_path=save_path)

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

        self.logger.info("Completed unsupervised training.")

    def rlhf_retraining(self, path: str):
        with open(path, "r") as file:
            for line in file:
                feedback = FeedbackLog.model_validate_json(line)
                if feedback.event.action == ActionType.upvote:
                    self.db.upvote(
                        queries=feedback.event.queries,
                        chunk_ids=feedback.event.chunk_ids,
                    )
                elif feedback.event.action == ActionType.associate:
                    self.db.associate(
                        sources=feedback.event.sources,
                        targets=feedback.event.targets,
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
            self.logger.info("Completed Unsupervised Training")

        if supervised_files:
            self.logger.info(f"Found {len(supervised_files)} supervised files.")
            check_disk(self.db, self.config.model_bazaar_dir, supervised_files)
            self.supervised_train(supervised_files)
            self.logger.info("Completed Supervised Training")

        train_time = time.time() - start_time
        self.logger.info(f"Total training time: {train_time} seconds")

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
