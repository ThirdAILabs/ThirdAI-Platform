from transformers import AutoModelForMaskedLM, AutoModelForSequenceClassification

model = AutoModelForSequenceClassification.from_pretrained(
    "jinaai/jina-reranker-v1-tiny-en", num_labels=1, trust_remote_code=True
)

model = AutoModelForMaskedLM.from_pretrained("naver/splade-cocondenser-selfdistil")
