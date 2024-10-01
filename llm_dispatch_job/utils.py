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
    "Write an answer that is about 100 words "
    + "for the query, based on the provided context. "
    + "If the context provides insufficient information, "
    + 'reply "I cannot answer", and give a reason why. '
    + "Answer in an unbiased, comprehensive, and scholarly tone. "
    + "If the query is subjective, provide an opinionated answer "
    + "in the concluding 1-2 sentences. "
    + "If the given query is not answerable or is not a question, "
    + "simply summarize the given context as coherently as possible."
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
    query: str, prompt: Optional[str], references: List[Reference]
):
    if prompt or references:
        context = "\n\n".join(map(reference_content, references))
        context = " ".join(context.split(" ")[:2000])

        return f"{prompt or DEFAULT_PROMPT}\n\nContext: '{context}'\nQuery: '{query}'\nAnswer: "

    return query
