from database import schema
from sqlalchemy.orm import Session

default_workflow_types = [
    {
        "name": "semantic_search",
        "description": "Semantic search workflow",
        "model_requirements": [[{"component": "search", "type": "ndb"}]],
    },
    {
        "name": "nlp",
        "description": "NLP workflow",
        "model_requirements": [[{"component": "nlp", "type": "udt"}]],
    },
    {
        "name": "rag",
        "description": "RAG workflow",
        "model_requirements": [
            [
                {"component": "search", "type": "ndb"},
                {"component": "guardrail", "type": "udt", "subtype": "token"},
            ],
            [
                {"component": "search", "type": "ndb"},
            ],
            [
                {"component": "search", "type": "ndb"},
                {"component": "guardrail", "type": "udt", "subtype": "token"},
                {"component": "sentiment", "type": "udt", "subtype": "text"},
            ],
        ],
    },
    {
        "name": "chatbot",
        "description": "Chatbot workflow",
        "model_requirements": [
            [
                {"component": "search", "type": "ndb"},
                {"component": "guardrail", "type": "udt", "subtype": "token"},
            ],
            [
                {"component": "search", "type": "ndb"},
            ],
            [
                {"component": "search", "type": "ndb"},
                {"component": "guardrail", "type": "udt", "subtype": "token"},
                {"component": "sentiment", "type": "udt", "subtype": "text"},
            ],
        ],
    },
]


def initialize_default_workflow_types(session: Session):
    for workflow_type in default_workflow_types:
        existing_type = (
            session.query(schema.WorkflowType)
            .filter_by(name=workflow_type["name"])
            .first()
        )
        if existing_type:
            # If the model_requirements don't match, update them
            if existing_type.model_requirements != workflow_type["model_requirements"]:
                existing_type.model_requirements = workflow_type["model_requirements"]
                session.add(existing_type)

        else:
            new_workflow_type = schema.WorkflowType(
                name=workflow_type["name"],
                description=workflow_type["description"],
                model_requirements=workflow_type["model_requirements"],
            )
            session.add(new_workflow_type)
    session.commit()
