import os


def doc_dir():
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "thirdai_platform/train_job/sample_docs/",
    )
