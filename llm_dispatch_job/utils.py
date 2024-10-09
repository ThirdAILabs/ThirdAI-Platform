from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Reference(BaseModel):
    text: str
    source: Optional[str] = None
    metadata: Dict[str, Any] = {}


class GenerateArgs(BaseModel):
    query: str
    task_prompt: Optional[str] = None
    references: List[Reference] = []

    key: Optional[str] = None
    model: str = "gpt-4o-mini"
    provider: str = "openai"
    workflow_id: Optional[str] = None

    cache_access_token: Optional[str] = None


DEFAULT_SYSTEM_PROMPT = (
    "Write a short answer for the user's query based on the provided context. "
    "If the context provides insufficient information, mention it but answer to "
    "the best of your abilities."
)

DEFAULT_PROMPT = "Given this context, "


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


def make_prompt(
    query: str,
    task_prompt: Optional[str],
    references: List[Reference],
    reverse_ref_order: bool = False,
    token_limit: int = 2000,
):
    if reverse_ref_order:
        references = references[::-1]

    processed_references = map(reference_content, references)
    context = "\n\n".join(processed_references)

    if reverse_ref_order:
        context = " ".join(context.split(" ")[-token_limit:])
    else:
        context = " ".join(context.split(" ")[:token_limit])

    system_prompt = DEFAULT_SYSTEM_PROMPT
    user_prompt = f"{context}\n\n {task_prompt or DEFAULT_PROMPT} {query}"

    return system_prompt, user_prompt
