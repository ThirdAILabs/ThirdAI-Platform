datagen_prompt = """This is the description of the task user wants to perform: ```{task_prompt}```
Generate {samples_to_generate} training samples for above task for the label "{label_name}".

The data generated should strictly follow the description: 
{label_name}: {label_description}

Output Format:
- Each sample should be in a newline.
- DO NOT include any enumeration, bulleting, prefix/suffix or any processes involved. Do not include any quotes or emojis.

Ensure that the data is diverse enough to capture different genres and dialects.
Do not include the label in sentences.
Try to generate samples containing {min_sample_len} to {max_sample_len} number of words.

Following are some of the sample data points for reference:
{examples}

Don't generate these exact examples.

{user_prompts}
You can refer to these prompt to include diversity:
{random_prompts}

You can following words to generate diverse samples:
{random_vocab}
"""
