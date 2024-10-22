COMMON_PATTERNS = {
    "CREDITCARDNUMBER",
    "EMAIL",
    "PHONENUMBER",
    "MEDICAL_LICENSE",
    "BANK_NUMBER",
    "SSN",
    "IBAN",
    "CREDITCARDCVV",
    "USDRIVERSLICENSE",
    "USPASSPORT",
    "IPADDRESS",
}


def find_common_pattern(entity: str) -> str:
    if entity.upper() in COMMON_PATTERNS:
        return entity.upper()
    return None
