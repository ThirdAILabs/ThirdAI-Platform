datagen_prompt = """This is the description of the task user wants to perform: ```{task_prompt}```
Generate {samples_to_generate} training samples for above task for the label "{label_to_generate}".

The data generated should strictly follow the description: 
{label_description}

DO NOT include any bulleting or prefix at start of each sentence and each. Do not include any quotes or emojis.


VERY IMPORTANT POINT: Give only the sentences in output and make sure each sentence should start on a new line. Do not include any extra new line.


Ensure that the data is diverse enough to capture different genres and dialects.
Do not include the label in sentences.

Following are some of the sample data points for reference:
{examples}

GENERATED SAMPLES MUST BE VERY DIFFERENT FROM THE ABOVE SAMPLES

{user_prompts}
You can refer to these prompt to include diversity:
{random_prompts}

Sentences should have following words to generate diverse examples:
{random_vocab}
"""
