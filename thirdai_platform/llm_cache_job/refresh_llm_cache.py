pass
import logging
import os
from pathlib import Path

pass
import glob

from licensing.verify import verify_license
from llm_cache_job.cache import Cache, NDBSemanticCache
from llm_cache_job.reporter import HttpReporter
from llm_cache_job.utils import CacheInsertLog
from platform_common.logging import setup_logger

license_key = os.getenv("LICENSE_KEY")
verify_license.activate_thirdai_license(license_key)

model_bazaar_dir = os.getenv("MODEL_BAZAAR_DIR")
model_id = os.getenv("MODEL_ID")
model_dir = Path(model_bazaar_dir) / "models" / model_id
log_dir: Path = Path(model_bazaar_dir) / "logs" / model_id


def main():
    setup_logger(log_dir=log_dir, log_prefix="llm-cache")

    logger = logging.getLogger("llm-cache")

    reporter = HttpReporter(os.getenv("MODEL_BAZAAR_ENDPOINT"), logger)

    reporter.report_status(model_id, "in_progress")

    try:
        # TODO does this work while deploying?
        cache_ndb_path = os.path.join(model_dir, "llm_cache", "llm_cache.ndb")
        cache: Cache = NDBSemanticCache(
            cache_ndb_path=cache_ndb_path, log_dir=model_dir, logger=logger
        )

        insertions_folder = os.path.join(
            model_dir, "llm_cache", "insertions", "new", "*.jsonl"
        )
        insertion_files = glob.glob(insertions_folder)

        insertions = []
        lines = []
        for insertion_file in insertion_files:
            with open(insertion_file) as f:
                for line in f.readlines():
                    lines.append(line)
                    log = CacheInsertLog.model_validate_json(line)
                    insertions.append(log)

        cache.insert(insertions)

        past_insertions_file = os.path.join(
            model_dir, "llm_cache", "insertions", "past_insertions.jsonl"
        )
        with open(past_insertions_file, "a") as f:
            for line in lines:
                f.write(line)

        for insertion_file in insertion_files:
            os.remove(insertion_file)
    except Exception as e:
        reporter.report_status(model_id, "failed", str(e))
        raise

    reporter.report_status(model_id, "complete")


if __name__ == "__main__":
    main()
