import os
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List

from platform_common.ndb.ndbv1_parser import parse_doc
from platform_common.pydantic_models.training import FileInfo, FileLocation
from thirdai import neural_db as ndb

GB_1 = 1024 * 1024 * 1024  # Define 1 GB in bytes


def check_csv_only(all_files: List[FileInfo]):
    for file in all_files:
        if file.ext() != ".csv":
            raise ValueError(
                "Only CSV files are supported for supervised training and test."
            )


def check_local_nfs_only(files: List[FileInfo]):
    for file in files:
        if file.location != FileLocation.local and file.location != FileLocation.nfs:
            raise ValueError(
                "Only local/nfs files are supported for supervised training/test."
            )


def producer(files: List[FileInfo], buffer, tmp_dir: str):
    """
    Process files in parallel and add the resulting NDB files to a buffer.
    """
    max_cores = os.cpu_count()
    num_workers = max(1, max_cores - 6)
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_file = {
            executor.submit(parse_doc, file, tmp_dir): file for file in files
        }

        for future in as_completed(future_to_file):
            file = future_to_file[future]
            try:
                ndb_file = future.result()
                if ndb_file and not isinstance(ndb_file, str):
                    buffer.put(ndb_file)
                    print(f"Successfully processed {file.path}", flush=True)
            except Exception as e:
                print(f"Error processing file {file}: {e}")

    buffer.put(None)  # Signal that the producer is done


def consumer(buffer, db, epochs: int = 5, batch_size: int = 10):
    """
    Consume NDB files from a buffer and insert them into NeuralDB in batches.
    """
    batch = []

    while True:
        ndb_doc = buffer.get()
        if ndb_doc is None:
            # Process any remaining documents in the last batch
            if batch:
                db.insert(batch, train=True, epochs=epochs)
            break

        batch.append(ndb_doc)

        # Process the batch if it reaches the batch size
        if len(batch) >= batch_size and buffer.qsize() == 0:
            db.insert(batch, train=True, epochs=epochs)
            batch.clear()


def check_disk(db, model_bazaar_dir: str, files: List[FileInfo]):
    """
    Check if there is enough disk space to process the files.
    """
    approx_ndb_size = 1.5 * sys.getsizeof(db) + 2 * sum(
        [os.path.getsize(file.path) for file in files if os.path.exists(file.path)]
    )

    available_nfs_storage = shutil.disk_usage(
        os.path.join(model_bazaar_dir, "models")
    ).free

    if available_nfs_storage < approx_ndb_size:
        print(
            f"Available NFS storage : {available_nfs_storage/GB_1} GB is less than approx model size : {approx_ndb_size/GB_1} GB."
        )
        raise Exception("Training aborted due to low disk space.")


def convert_supervised_to_ndb_file(file: FileInfo) -> ndb.Sup:
    """
    Convert a supervised training file to an NDB file.
    """
    if file.ext() == ".csv":
        return ndb.Sup(
            file.path,
            query_column=file.options.get("csv_query_column", None),
            id_delimiter=file.options.get("csv_id_delimiter", None),
            id_column=file.options.get("csv_id_column", None),
            source_id=file.doc_id,
        )
    else:
        raise TypeError(
            f"{file.ext()} file type is not supported for supervised training, only .csv files are supported."
        )


def get_directory_size(directory: Path) -> int:
    """
    Calculate the size of a directory in bytes.
    """
    size = 0
    for root, dirs, files in os.walk(directory):
        for name in files:
            size += os.stat(Path(root) / name).st_size
    return size
