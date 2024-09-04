from thirdai import neural_db as ndb

pdf = ndb.PDF("Ricepdf.pdf")


chunks = []
for i in range(0, 100, 3):
    chunks.append(
        pdf.table.df["para"][i]
        + pdf.table.df["para"][i + 1]
        + pdf.table.df["para"][i + 2]
    )


import pandas as pd


def ask_gpt(message):
    import time

    from openai import OpenAI

    client = OpenAI(
        # api_key="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" # fast one
        api_key="sk-PYTWB6gs_ofO44-teXA2rIRGRbJfzqDyNXBalHXKcvT3BlbkFJk5905SK2RVE6_ME8i4Lnp9qULbyPZSyOU0vh2fZfQA"
    )
    while True:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": message,
                    }
                ],
                temperature=0.1,
            )
            response_content = response.choices[0].message.content
            return response_content
        except Exception as e:
            print(e)
            time.sleep(5)


import tqdm

questions = []
for chunk in tqdm.tqdm(chunks):
    qs = ask_gpt(
        f"Can you please generate 3 different questions that can be answered with the following context. Make sure to ONLY return the three with no fluff. No numbers and only separated by new lines. Thanks GPT! Here is the context: {chunk}"
    )
    for q in qs.split("\n"):
        questions.append(q)

questions = [q for q in questions if q != ""]


import random


def perturb_string(input_string):
    num_chars_to_delete = random.randint(2, 3)
    char_list = list(input_string)
    for _ in range(num_chars_to_delete):
        if char_list:
            char_list.pop(random.randrange(len(char_list)))
    perturbed_string = "".join(char_list)
    return perturbed_string


perturbed_questions = [perturb_string(q) for q in questions]


unperturbed_in_cache = questions[:33]
perturbed_not_in_cache = perturbed_questions[:33]
unperturbed_not_in_cache = questions[34:67]
final_questions = (
    unperturbed_in_cache + perturbed_not_in_cache + unperturbed_not_in_cache
)

df = pd.DataFrame(
    {
        "in_cache": unperturbed_in_cache,
        "perturbed": perturbed_not_in_cache,
        "new_queries": unperturbed_not_in_cache,
    }
)
df.to_csv("questions.csv", index=False)
