attribute_dimension_prompt = """Which attribute dimensions do you consider most vital in determining the topic of the task: ```{domain_prompt}```?

DO NOT include any bulleting or prefix at start of each sentence and each. Do not include any quotes or emojis.

VERY IMPORTANT POINT: Give only the attributes in output and make sure each attribute should start on a new line. Do not include any extra new line.

List atmost 5 attributes.

Eg. If domain is news, topics can be
Sports
Healthcare
Politics
Stocks
Weather
"""

attribute_value_prompt = """Given your extensive expertise in {domain_prompt}, please provide a range of realistic values for {attribute}. Ensure these estimates are diverse and applicable to real-world scenarios. 
For attributes known to have well-defined values, provide specific, practical estimates; for all other attributes, offer generalized yet realistic ranges.

DO NOT include any bulleting or prefix at start of each sentence and each. Do not include any quotes or emojis.

VERY IMPORTANT POINT: Give only the attributes in output and make sure each attribute should start on a new line. Do not include any extra new line.
"""

tag_value_prompt = """You possess deep expertise in {domain_prompt}. Please generate {num_samples_per_tag} diverse samples for the {tag} named entity. Below are some examples of the {tag} entity:
{tag_example}

Ensure each sample starts on a new line without any bullet points, prefixes, quotes, or emojis at the beginning of each sentence.

VERY IMPORTANT: Only include the attributes themselves in the output. Each attribute should appear on a new line without any additional new lines.

Additionally, aim to cover a wide range of variations within the {tag} entity to ensure the data is as varied and representative as possible.
"""

template_prompt = """You have to generate {k} templatized sentences for the tags: {tags}

As an example here are two sentences for the tags [GENDER,ENTHNICITY,DISABILITY,SSN]

She is [GENDER] and is of [ENTHNICITY] DESCENT 
After getting diagnosed with [DISABILITY] John went home. His social security number is [SSN].

Each sentence should start on a new line and with no bulleting, header/footer or any steps involved.
"""

dataset_generation_prompt = """You possess deep expertise in {domain_prompt}. Please generate {num_to_generate} templates of synthetic sentences and associated tags for {domain_prompt}
            
VERY IMPORTANT: MAKE SURE identify all named entities occurred that belong to one of the following entity types: 
{sampled_tags}


When generating the output for the NER task, adhere to the following strict format guidelines to ensure data consistency and format correctness

Following are some sample output format for generation. This is just for example and you should not mimic this pattern.

{templatized_sentences_examples}

Key Requirements:
-   Mask only the Entities in square brackets with and make sure entities are in upper case. 
-   The entities should strictly belong to one of {sampled_tags}. Do not include anything apart from entities in square brackets
-   Seperate different samples by new line
-   Give only the generated samples in output and make sure each sample should start on a new line. Do not include any extra new line. 
-   DO NOT include any bulleting or prefix at start of each sentence and each. Do not include any quotes or emojis
-   Give equal weightage to all the tags
-   {rnd_prompts_str}

{values_requirements}
"""
