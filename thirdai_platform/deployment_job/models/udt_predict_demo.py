import re
from difflib import get_close_matches
from typing import List, Literal

from pydantic import BaseModel

common_entities = {
    "BRAND": [
        "APPLE",
        "GOOGLE",
        "VOLTAS",
        "LG",
        "Godrej",
        "Life's Good",
        "Whirlpool",
        "Daikin",
        "Samsung",
        "Bosch",
        "Hitachi",
        "Panasonic",
        "Blue Star",
        "Haier",
        "LLoyd",
        "Mitsubishi",
        # general electric things
        "General Electric",
        "GE",
        "General Electrics",
        "G Electric",
        "General E",
        # others
        "Frigidaire",
        "Kenmore",
    ],
    "MODEL_NUMBER": [
        # kenmore
        "75085",
        "76100",
        "75135",
        "75151",
        "75251",
        # frigidaire
        "FAM156R1A",
        "FAC102P1A",
        "FAH12ER2T",
        "FAA055P7A",
        # ge
        "ASH06LL",
        "ASH08FK",
        "AGM24DJ",
        # haier
        "HPM09XC5",
        "HPR09XC5",
        "HRPD12HC5",
        "HWR08XC7",
    ],
}


class UnstructuredTokenClassificationResults(BaseModel):
    data_type: Literal["unstructured"]
    query_text: str
    tokens: List[str]
    predicted_tags: List[List[str]]


MODEL_PATTERNS = [
    r"^AEH18.*$",  # Matches any string starting with AEH18
] + [re.escape(model) for model in common_entities["MODEL_NUMBER"]]


def tokenize(text: str) -> List[str]:
    # keep punctuation but remove whitespace
    tokens = re.findall(r"\w+|[^\w\s]", text)
    return tokens


def clean_token(token: str) -> str:
    # remove all non-alphanumeric characters
    return re.sub(r"[^\w\s]", "", token)


def fuzzy_match_entity(
    token: str, entity_list: List[str], threshold: float = 0.8
) -> bool:
    token = clean_token(token).upper()
    if not token:
        return False
    matches = get_close_matches(
        token, [e.upper() for e in entity_list], n=1, cutoff=threshold
    )
    return len(matches) > 0


def is_model_number(token: str) -> bool:
    token = clean_token(token).upper()
    if not token:
        return False
    return any(re.match(pattern, token, re.IGNORECASE) for pattern in MODEL_PATTERNS)


def check_multi_token_brand(
    tokens: List[str], start_idx: int, brands: List[str]
) -> int:
    # start from index start_idx
    # remove all tokens that do not have any alphanumeric characters
    # make map of index in cleaned tokens to index in original tokens
    # find out the max number of tokens that matches against a brand name
    # return the length of the brand name when split on spaces and the indices of the tokens in the original tokens list

    token_map = {}
    cleaned_tokens = []
    for index, token in enumerate(tokens):
        token = clean_token(token)
        if token.strip() == "":
            continue
        else:
            token_map[len(cleaned_tokens)] = index
            cleaned_tokens.append(token)

    # print(cleaned_tokens)
    # print(token_map)

    max_brand_tokens = max(len(brand.split()) for brand in brands)

    for length in range(max_brand_tokens, 0, -1):
        if start_idx + length > len(cleaned_tokens):
            continue

        combined = " ".join(cleaned_tokens[start_idx : start_idx + length])
        cleaned_combined = clean_token(combined)

        if not cleaned_combined:
            continue
        if fuzzy_match_entity(cleaned_combined, brands, threshold=0.9):
            matched_indices = []
            for i in range(length):
                matched_indices.append(token_map[start_idx + i])
            return length, matched_indices
    return 0, None


def predict(
    text: str, data_type: str = "unstructured", **kwargs
) -> UnstructuredTokenClassificationResults:

    if "verbose" in kwargs and kwargs["verbose"]:
        VERBOSE = True
    else:
        VERBOSE = False

    tokens = tokenize(text)
    tags = ["O"] * len(tokens)

    i = 0
    while i < len(tokens):
        if VERBOSE:
            print(f"{i=}, {tokens[i]=}")

        consecutive_token_match_length, matched_indices = check_multi_token_brand(
            tokens, i, common_entities["BRAND"]
        )

        if consecutive_token_match_length > 0:
            if VERBOSE:
                print(f"{consecutive_token_match_length=}")
                print(
                    f"matched brand multiple tokens: {tokens[i : i + consecutive_token_match_length]}",
                )

            for index in matched_indices:
                tags[index] = "BRAND"

            i += consecutive_token_match_length
            continue

        token = tokens[i]

        if fuzzy_match_entity(token, common_entities["BRAND"]):
            if VERBOSE:
                print(f"matched brand single token: {token}")
            tags[i] = "BRAND"

        elif fuzzy_match_entity(token, common_entities["MODEL_NUMBER"]):
            if VERBOSE:
                print(f"matched model number single token: {token}")
            tags[i] = "MODEL_NUMBER"

        # Check for AEH18 pattern
        elif is_model_number(token):
            if VERBOSE:
                print(f"matched model number AEH18 pattern: {token}")
            tags[i] = "MODEL_NUMBER"

        i += 1
    results = UnstructuredTokenClassificationResults(
        data_type="unstructured",
        query_text=text,
        tokens=tokens,
        predicted_tags=[[tag] for tag in tags],
    )

    return results
