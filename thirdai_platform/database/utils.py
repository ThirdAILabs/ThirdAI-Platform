from database import schema
from sqlalchemy.orm import Session

default_workflow_types = [
    {
        "name": "semantic_search",
        "description": "Semantic search workflow",
        "model_requirements": {
            "ndb": {"count": 1},
        },
    },
    {
        "name": "nlp",
        "description": "NLP workflow",
        "model_requirements": {"udt": {"count": 1}},
    },
    {
        "name": "rag",
        "description": "RAG workflow",
        "model_requirements": {
            "ndb": {"count": 1},
            "udt": {"count": 1, "sub_type": "token"},
        },
    },
]


def initialize_default_workflow_types(session: Session):
    for workflow_type in default_workflow_types:
        existing_type = (
            session.query(schema.WorkflowType)
            .filter_by(name=workflow_type["name"])
            .first()
        )
        if not existing_type:
            new_workflow_type = schema.WorkflowType(
                name=workflow_type["name"],
                description=workflow_type["description"],
                model_requirements=workflow_type["model_requirements"],
            )
            session.add(new_workflow_type)
    session.commit()
