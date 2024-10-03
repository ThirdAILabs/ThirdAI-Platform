import os


def doc_dir():
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "train_job/sample_docs/"
    )
