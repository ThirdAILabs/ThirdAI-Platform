import random
import re
from collections import defaultdict
from resource.token_prompts import dataset_generation_prompt, tag_value_prompt
from typing import Any, Dict, List, Optional

from data_factory_interface import DataFactory
from faker import Faker
from tqdm import tqdm
from utils import (
    remove_duplicates,
    save_dict,
    shuffle_and_filter,
    train_test_split,
    write_to_csv,
)
from variables import Entity


class TokenDataFactory(DataFactory):
    SOURCE_COLUMN = "source"
    TARGET_COLUMN = "target"

    def __init__(
        self,
    ):
        super().__init__()
        self.faker = Faker()
        self.sentences_per_template = 4

        # All methods present in the faker to generate forged tags. E.g: credit_card_expire(), credit_card_expire(), first_name(), language_name(), ..
        self.faked_methods = [
            method
            for provider in self.faker.providers
            for method in dir(provider)
            if not method.startswith("_")
        ]

    # Function to generate the tag_values by faker library
    def get_tag_values_from_faker(self, tag: str, num_samples: int):
        # NOTE: It could be better to have an exact match
        matched_attrs = list(
            filter(lambda method: tag.lower() == method.lower(), self.faked_methods)
        )

        if not matched_attrs:
            return []

        return list(
            map(
                lambda x: str(x),
                [
                    self.faker.__getattr__(random.choice(matched_attrs))()
                    for _ in range(num_samples)
                ],
            ),
        )

    def get_tag_values_from_llm(
        self,
        task_prompt: str,
        tag: Entity,
        values_to_generate: int,
        complete_tag_values: Dict[str, List[str]],
        generate_at_a_time: int = 100,
    ):
        sampled_tag_values = random.sample(tag.examples, k=min(3, len(tag.examples)))

        # Collecting prompts
        arguments = []
        for idx in range(0, values_to_generate, generate_at_a_time):
            arguments.append(
                {
                    "prompt": tag_value_prompt.format(
                        task_prompt=task_prompt,
                        num_samples_per_tag=min(
                            generate_at_a_time,
                            values_to_generate - idx,
                        ),
                        tag=tag.name,
                        tag_example=str(sampled_tag_values),
                        tag_description=tag.description,
                    ),
                }
            )
        total_chunks = len(arguments) // self.write_chunk_size + 1

        # Making llm call with collected prompts parallelly.
        for idx in tqdm(
            range(0, len(arguments), self.write_chunk_size),
            desc=f"Generating {tag.name} values: ",
            total=total_chunks,
            leave=False,
        ):
            # TODO(Gautam): If there are limited values to a tag, only should make call to get those many values atmost.
            chunks_to_process = arguments[idx : idx + self.write_chunk_size]

            responses: List[Dict[str, Any]] = self.run_and_collect_results(
                tasks_prompt=chunks_to_process, parallelize=True
            )

            generated_tag_values = [
                value.strip()
                for res in responses
                for value in res["response_text"].split("\n")
            ]

            complete_tag_values[tag.name].extend(generated_tag_values)
            save_dict(write_to=self.save_dir / "tags_value.json", **complete_tag_values)

    # Function to generate the tag_values by using faker library or LLM calls.
    def get_tag_values(
        self,
        task_prompt: str,
        tags: List[Entity],
        values_to_generate: int,
        generate_at_a_time: int = 100,
    ) -> Dict[str, List[str]]:
        complete_tag_values = defaultdict(list)

        for tag in tqdm(tags, desc="Generating values for tags: ", leave=False):
            complete_tag_values[tag.name].extend(tag.examples)

            # Trying to generate more examples from faker
            samples = self.get_tag_values_from_faker(
                tag.name,
                num_samples=int(
                    values_to_generate * 1.5
                ),  # Assuming after removing duplicates, we'll have `values_to_generate` tag values
            )

            if samples:
                save_dict(
                    write_to=self.save_dir / "tags_value.json", **complete_tag_values
                )
                complete_tag_values[tag.name].extend(samples)
                continue

            # Not able to generate by faker so, generating samples by llm
            samples = self.get_tag_values_from_llm(
                task_prompt=task_prompt,
                tag=tag,
                values_to_generate=values_to_generate,
                complete_tag_values=complete_tag_values,
                generate_at_a_time=generate_at_a_time,
            )

        complete_tag_values = {
            tag_name: remove_duplicates(values)
            for tag_name, values in complete_tag_values.items()
        }
        save_dict(write_to=self.save_dir / "tags_value.json", **complete_tag_values)
        return complete_tag_values

    # Function to split the tag_values to train/test set.
    def train_test_tag_split(
        self,
        tag_values: Dict[str, List[str]],
        test_size: Optional[float] = None,
        shuffle: bool = True,
        save: bool = True,
    ):
        if shuffle:
            for tag_name, values in tag_values.items():
                random.shuffle(values)

        if not test_size:
            if save:
                save_dict(self.save_dir / "train" / "tag_values.json", **tag_values)

            return tag_values, None

        train_tags, test_tags = {}, {}
        for tag_name, values in tag_values.items():
            split_index = int(len(values) * (1 - test_size))
            train_tags[tag_name] = values[:split_index]
            test_tags[tag_name] = values[split_index:]

        if save:
            save_dict(self.save_dir / "train" / "tag_values.json", **train_tags)
            save_dict(self.save_dir / "test" / "tag_values.json", **test_tags)

        return train_tags, test_tags

    # Function to calculate the number of templates to generate
    def _templates_to_generate(self, num_sentences_to_generate: int):
        return (
            num_sentences_to_generate - self.train_sentences_generated
        ) // self.sentences_per_template

    def _subsample_tag(self, tags: List[Entity], k: int = 4):
        return random.sample(tags, min(len(tags), k))

    def collect_prompts(
        self,
        tags: List[Entity],
        templates_to_generate: int,
        task_prompt: str,
        tag_values: Dict[str, List[str]],
    ):
        extended_tag_description = self.get_extended_description(entities=tags)

        arguments = []
        for current_sentence_idx in range(
            0, templates_to_generate, self.generate_at_a_time
        ):
            # TODO(anyone): we should also add the [user_tag -> examples] in dataset_generation_prompt.
            sampled_tags = self._subsample_tag(tags, k=4)

            arguments.append(
                {
                    "prompt": dataset_generation_prompt.format(
                        task_prompt=task_prompt,
                        num_to_generate=min(
                            templates_to_generate - current_sentence_idx,
                            self.generate_at_a_time,
                        ),
                        tags_info="\n\n".join(
                            [
                                f"""
Tag: {tag.name}
Description: {tag.description}. {extended_tag_description[tag.name]}
Example: {str(random.sample(tag_values[tag.name], k = 2))} not limited to given but variations as well.
""".strip(
                                    "\n"
                                )
                                for tag in sampled_tags
                            ]
                        ),
                        value_requirements="\n- ".join(self.get_random_prompts(k=2)),
                    ),
                    "system_prompt": f"You are a helpful assistant designed to generate synthetic data for domain {task_prompt}.",
                }
            )

        return arguments

    def generate_data(
        self,
        task_prompt: str,
        tags: List[Entity],
        num_sentences_to_generate: int,
        num_samples_per_tag: Optional[int] = None,
    ):
        templates_to_generate = self._templates_to_generate(num_sentences_to_generate)
        """
        Generating the tag values
        Example: 
            Tags: [CREDIT_CARD_NUMBER, CVV]

            CREDIT_CARD_NUMBER = [568598651245, 7895-7895-3526-9184,..]
            CVV = [285, 569,..]
        """
        tag_values = self.get_tag_values(
            task_prompt=task_prompt,
            tags=tags,
            values_to_generate=num_samples_per_tag
            or (templates_to_generate * self.sentences_per_template),
        )

        # Splitting the tag values into train and test set.
        train_tag_values, test_tag_values = self.train_test_tag_split(
            tag_values=tag_values,
            test_size=self.general_variables.test_size * self.sentences_per_template,
            shuffle=True,
            save=True,
        )

        # Creating a prompt list to be executed parallelly.
        arguments = self.collect_prompts(
            tags=tags,
            templates_to_generate=templates_to_generate,
            task_prompt=task_prompt,
            tag_values=tag_values,
        )

        random.shuffle(arguments)
        total_chunks = len(arguments) // self.write_chunk_size + 1
        for idx in tqdm(
            range(0, len(arguments), self.write_chunk_size),
            desc="Generating token data: ",
            total=total_chunks,
        ):
            chunks_to_process = arguments[idx : idx + self.write_chunk_size]

            # parallelly make the {self.write_chunk_size} number of LLM calls.
            generated_templates: List[Dict[str, Any]] = self.run_and_collect_results(
                tasks_prompt=chunks_to_process, parallelize=True
            )

            """
            Processing to convert each llm call's generated text to a list of templates
            """
            templates = [
                template.strip('" ')
                for template_s in generated_templates
                for template in template_s["response_text"].split("\n")
            ]
            templates = shuffle_and_filter(templates)

            # Splitting into train/test template set
            train_templates, test_templates = train_test_split(
                data_points=templates, test_size=self.general_variables.test_size
            )
            # Saving the train and test templates
            if train_templates:
                # It should always be present, but incase test_size is set to 1.0
                write_to_csv(
                    path=self.save_dir / "train" / "templates.csv",
                    data_points=[
                        {"template": template} for template in train_templates
                    ],
                    fieldnames=["template"],
                )
            if test_templates:
                write_to_csv(
                    path=self.save_dir / "test" / "templates.csv",
                    data_points=[{"template": template} for template in test_templates],
                    fieldnames=["template"],
                )

            if train_templates:
                # Filling the train-templates with the train-tag-values and saving it.
                train_datapoints = [
                    item
                    for template in train_templates
                    for item in self.fill_and_transform(
                        template=template,
                        tag_values=train_tag_values,
                        sentences_to_generate=self.sentences_per_template,
                    )
                ]
                train_datapoints = shuffle_and_filter(train_datapoints)

                if train_datapoints:
                    # It should always be present, but incase test_size is set to 1.0
                    write_to_csv(
                        self.train_file_location,
                        train_datapoints,
                        fieldnames=[
                            TokenDataFactory.SOURCE_COLUMN,
                            TokenDataFactory.TARGET_COLUMN,
                        ],
                    )
                    self.train_sentences_generated += len(train_datapoints)

            # Filling the test-templates with the test-tag-values and saving it.
            if test_templates:
                test_datapoints = [
                    item
                    for template in test_templates
                    for item in self.fill_and_transform(
                        template=template,
                        tag_values=test_tag_values,
                        sentences_to_generate=1,
                    )
                ]
                test_datapoints = shuffle_and_filter(test_datapoints)

                if test_datapoints:
                    write_to_csv(
                        self.test_file_location,
                        test_datapoints,
                        fieldnames=[
                            TokenDataFactory.SOURCE_COLUMN,
                            TokenDataFactory.TARGET_COLUMN,
                        ],
                    )
                self.test_sentences_generated += len(test_datapoints)

        # Generated dataset config.
        dataset_config = {
            "filepath": str(self.train_file_location),
            "error_file": str(self.errored_file_location),
            "task": "TOKEN_CLASSIFICATION",
            "input_feature": TokenDataFactory.SOURCE_COLUMN,
            "target_feature": TokenDataFactory.TARGET_COLUMN,
            "target_labels": [tag.name for tag in tags],
            "train_samples": self.train_sentences_generated,
            "test_samples": self.test_sentences_generated,
        }
        save_dict(self.config_file_location, **dataset_config)

        return dataset_config

    def fill_and_transform(
        self,
        template: str,
        tag_values: Dict[str, List[str]],
        sentences_to_generate: int,
    ) -> List[str]:
        if not template:
            return [None]

        seperator = " "
        words = template.split(sep=seperator)

        data_points = [
            {TokenDataFactory.SOURCE_COLUMN: [], TokenDataFactory.TARGET_COLUMN: []}
            for _ in range(sentences_to_generate)
        ]

        for word in words:
            match = re.search(r"\[(.*?)\]", word)
            if match:
                # word is a tag
                word_tag = match.group(1).upper()
                if word_tag not in tag_values:
                    self.write_on_errorfile(
                        text=f"Tag {word_tag} not present in the allowed tags {', '.join(tag_values.keys())}\n"
                        + f"template: {template}\n"
                    )
                    return [None]

                for idx in range(sentences_to_generate):
                    splitted_word_tag_value = random.choice(tag_values[word_tag]).split(
                        sep=seperator
                    )
                    data_points[idx][TokenDataFactory.SOURCE_COLUMN].extend(
                        splitted_word_tag_value
                    )

                    """
                    Extending the [TAG] to match the source text

                        For example:
                            template = '[NAME] reserved the hall for reunion'
                            word_tag = [NAME]
                            word_tag_value = Jessica vega
                            splitted_word_tag_value = ['Jessica', 'vega']

                        Expected:
                            source = 'Jessica vega reserved the hall for reunion'
                            target = 'NAME NAME O O O O O'
                    """
                    data_points[idx][TokenDataFactory.TARGET_COLUMN].extend(
                        [word_tag] * len(splitted_word_tag_value)
                    )
            else:
                for idx in range(sentences_to_generate):
                    data_points[idx][TokenDataFactory.SOURCE_COLUMN].append(
                        word.strip()
                    )
                    data_points[idx][TokenDataFactory.TARGET_COLUMN].append("O")

        # make sure that the source and target is of same length
        sentences = []
        for data in data_points:
            if len(data[TokenDataFactory.SOURCE_COLUMN]) != len(
                data[TokenDataFactory.TARGET_COLUMN]
            ):
                self.write_on_errorfile(
                    text=f"Source and target aren't of the same length {'-' * 30}\n"
                    + f"source: {data[TokenDataFactory.SOURCE_COLUMN]}\n"
                    + f"target: {data[TokenDataFactory.TARGET_COLUMN]}\n"
                    + f"\n\ntemplate: {template}\n"
                )
            else:
                sentences.append(
                    {
                        TokenDataFactory.SOURCE_COLUMN: seperator.join(
                            data[TokenDataFactory.SOURCE_COLUMN]
                        ),
                        TokenDataFactory.TARGET_COLUMN: seperator.join(
                            data[TokenDataFactory.TARGET_COLUMN]
                        ),
                    }
                )

        return sentences
