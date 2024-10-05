from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Reference(BaseModel):
    text: str
    source: Optional[str] = None
    metadata: Dict[str, Any] = {}


class GenerateArgs(BaseModel):
    query: str
    prompt: Optional[str] = None
    references: List[Reference] = []

    key: Optional[str] = None
    model: str = "gpt-4o-mini"
    provider: str = "openai"
    workflow_id: Optional[str] = None

    cache_access_token: Optional[str] = None


DEFAULT_PROMPT = (
    "Write a short answer "
    + "for the query, based on the provided context. "
    + "If the context provides insufficient information, "
    + 'reply "I cannot answer".'
)


def reference_content(reference: Reference) -> str:
    if (
        reference.source
        and reference.source.endswith(".pdf")
        or reference.source.endswith(".docx")
    ):
        return f'(From file "{reference.source}") {reference.text}'
    if "title" in reference.metadata:
        return f'(From file "{reference.metadata["title"]}") {reference.text}'
    return f"(From a webpage) {reference.text}"


def combine_query_and_context(
    query: str,
    prompt: Optional[str],
    references: List[Reference],
    reverse_ref_order: bool = False,
):
    if prompt or references:
        if reverse_ref_order:
            references = references[::-1]
        processed_references = map(reference_content, references)
        context = "\n\n".join(processed_references)
        context = " ".join(context.split(" ")[:2000])

        return f"Context: '{context}'\n\n Prompt: {prompt or DEFAULT_PROMPT}\n\nQuery: '{query}'\n\nAnswer: "

    return query
