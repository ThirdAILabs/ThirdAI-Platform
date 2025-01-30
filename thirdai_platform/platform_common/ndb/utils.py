import os
from typing import List, Union
import shutil

from thirdai import neural_db_v2 as ndb


def delete_docs_and_remove_files(
    db: Union[ndb.NeuralDB, ndb.FastDB],
    doc_ids: List[str],
    full_documents_path: str,
    keep_latest_version: bool = False,
):

    deleted_filenames = set([])
    
    if isinstance(db, ndb.NeuralDB):
        for doc_id in doc_ids:
            deleted_chunks = db.delete_doc(
                doc_id, keep_latest_version=keep_latest_version, return_deleted_chunks=True
            )
            deleted_filenames.update([chunk.document for chunk in deleted_chunks])

    elif isinstance(db, ndb.FastDB):
        sources = db.documents()
        doc_id_to_source = {doc.doc_id: doc.document for doc in sources}
        for doc_id in doc_ids:
            deleted_chunks = db.delete_doc(
                doc_id, keep_latest_version=keep_latest_version
            )
            deleted_filenames.add(doc_id_to_source[doc_id])

    for deleted_filename in deleted_filenames:
        full_file_path = os.path.dirname(os.path.join(full_documents_path, deleted_filename))
        if os.path.exists(full_file_path):
            shutil.rmtree(full_file_path)
