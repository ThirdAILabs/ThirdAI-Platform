extended_description_prompt = """The goal is to get a comprehensive description of the given attribute. Please generate an extended description of the attribute {attribute_name}. Below are the user's example and description of the attribute

Attribute with it's user description and example:
Name: {attribute_name}
User description: {attribute_user_description}
Examples: {attribute_examples}

For example,
Attribute: PAN
User description: Patterns that match primary account number formats (typically 16-digit numbers)
Examples: [4587-8918-4578-2688, 124556893256]

==> Extended-description: A Primary Account Number (PAN) is a 16-digit number on credit/debit cards, including the Issuer Identification Number (IIN) and account number, following patterns like Visa (4###) and MasterCard (5###).

Output format:
-  Only output the extended description within 50-70 words
-  DO NOT include any bulleting, header/footer, enumeration, prefix/suffix or any process involved. Do not include any quotes or emojis.
"""
