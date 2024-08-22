import random
import re
from collections import defaultdict
from resource.token_prompts import (
    attribute_dimension_prompt,
    attribute_value_prompt,
    dataset_generation_prompt,
    tag_value_prompt,
    template_prompt,
)
from typing import Dict, List

from data_factory_interface import DataFactory
from faker import Faker
from tqdm import tqdm
from utils import assert_sufficient_examples, save_dict, subsample_dictionary


class TokenDataFactory(DataFactory):
    SOURCE_COLUMN = "source"
    TARGET_COLUMN = "target"

    def __init__(
        self,
    ):
        super().__init__()
        self.faker = Faker()

        # All methods present in the faker to generate forged tags. E.g: credit_card_expire(), credit_card_expire(), first_name(), language_name(), ..
        self.faked_methods = [
            method
            for provider in self.faker.providers
            for method in dir(provider)
            if not method.startswith("_")
        ]

    def get_attributes(self, domain_prompt: str):
        response: str = self.llm_model.completion(
            prompt=attribute_dimension_prompt.format(domain_prompt=domain_prompt),
        )
        attributes = response.split("\n")

        attribute_values = {}
        for attribute in tqdm(attributes, desc="Attributed definition...", leave=True):
            response = self.llm_model.completion(
                prompt=attribute_value_prompt.format(
                    domain_prompt=domain_prompt, attribute=attribute
                ),
            )
            attribute_values[attribute] = response.split("\n")

        return attribute_values

    def get_fake_tag_values(self, tag: str, num_samples: int):
        # NOTE: It could be better to have an exact match
        matched_attrs = list(
            filter(lambda method: tag.lower() in method.lower(), self.faked_methods)
        )
        if not matched_attrs:
            return []

        matched_attr = min(matched_attrs, key=len)

        return [self.faker.__getattr__(matched_attr)() for _ in range(num_samples)]

    def get_complete_tag_examples(
        self,
        domain_prompt: str,
        tag_examples: Dict[str, List[str]],
        total_expected_sentences: int,
        num_samples_per_tag: int,
    ):
        complete_tag_examples = defaultdict(list)

        for tag, user_examples in tqdm(
            tag_examples.items(), desc="Generating Sample for attributes: ", leave=True
        ):
            # Adding user examples
            complete_tag_examples[tag].extend(user_examples)

            # Trying to generate more examples from faker
            samples = self.get_fake_tag_values(
                tag,
                num_samples=total_expected_sentences,
            )
            if samples:
                complete_tag_examples[tag].extend(samples)
                continue

            # Not able to generate by faker so, generating samples by llm
            sampled_user_examples = random.sample(
                user_examples, min(3, len(user_examples))
            )

            response = self.llm_model.completion(
                prompt=tag_value_prompt.format(
                    domain_prompt=domain_prompt,
                    num_samples_per_tag=num_samples_per_tag,
                    tag=tag,
                    tag_example=str(sampled_user_examples),
                )
            )
            complete_tag_examples[tag].extend(response.split("\n"))

        return complete_tag_examples

    def get_templatized_examples(self, tags: List[str], k: int = 2):
        return self.llm_model.completion(
            template_prompt.format(tags=", ".join(tags).replace("'", ""), k=k)
        )

    def get_value_requirements(self, attribute_values: Dict[str, List[str]]):
        subsampled_dict = subsample_dictionary(attribute_values)
        sampled_keys = random.sample(
            [*subsampled_dict], k=min(10, len(subsampled_dict))
        )

        values_requirements = "Take inspiration from the ideas below but do not mimic them directly. Ensure your output revolves around similar topics with some variations for accuracy.\n"
        for key in sampled_keys:
            values = subsampled_dict[key]
            values_requirements += (
                f"Include the following {key}: {' and '.join(values)}.\n"
            )

        return values_requirements

    def generate_data(
        self,
        domain_prompt: str,
        tags: List[str],
        tag_examples: Dict[str, List[str]],
        num_sentences_to_generate: int,
        num_samples_per_tag: int = 4,
        sentences_generated=0,  # To resume the generate function incase of midway failure. TODO(Gautam): Incorporate resuming the data_generation task
    ):
        assert sentences_generated < num_sentences_to_generate, "Invalid configuration"

        assert_sufficient_examples(tags, tag_examples)

        attribute_values = self.get_attributes(domain_prompt)

        complete_tag_examples = self.get_complete_tag_examples(
            domain_prompt, tag_examples, num_sentences_to_generate, num_samples_per_tag
        )  # Here num_sentences_to_generate is used by faker to generate this many value of each tag.

        templatized_sentences_examples = self.get_templatized_examples(
            tags=random.sample(tags, k=min(10, len(tags)))
        )

        arguments = []
        for current_sentence_idx in range(
            0, num_sentences_to_generate, self.generate_at_a_time
        ):
            # TODO(anyone): we should also add the [user_tag -> examples] in dataset_generation_prompt.
            random_prompts = self.get_random_prompts()

            values_requirements = self.get_value_requirements(attribute_values)
            arguments.append(
                {
                    "prompt": dataset_generation_prompt.format(
                        domain_prompt=domain_prompt,
                        num_to_generate=min(
                            self.generate_at_a_time,
                            num_sentences_to_generate - current_sentence_idx,
                        ),
                        sampled_tags=random.sample(tags, k=min(5, len(tags))),
                        templatized_sentences_examples=templatized_sentences_examples,
                        rnd_prompts_str="\n -\t".join(random_prompts),
                        values_requirements=values_requirements,
                    ),
                    "system_prompt": f"You are a helpful assistant designed to generate synthetic data for domain {domain_prompt}.",
                }
            )

        random.shuffle(arguments)
        arguments = arguments[: num_sentences_to_generate - sentences_generated]
        self.write_chunk_size = 40

        total_chunks = len(arguments) // self.write_chunk_size + 1
        for idx in tqdm(
            range(0, len(arguments), self.write_chunk_size),
            desc="Generating token data: ",
            total=total_chunks,
        ):
            chunk_to_process = arguments[idx : idx + self.write_chunk_size]

            generated_templates: List[str] = self.run_and_collect_results(
                tasks_prompt=chunk_to_process, parallelize=True
            )

            transformed_data_points = [
                self.fill_and_transform(tags, template, complete_tag_examples)
                for template_s in generated_templates
                for template in template_s["response_text"].split("\n")
            ]
            # filtering to remove 'None'
            transformed_data_points = list(
                filter(lambda x: x is not None, transformed_data_points)
            )

            random.shuffle(transformed_data_points)

            self.write_on_training_file(
                transformed_data_points,
                fieldnames=[
                    TokenDataFactory.SOURCE_COLUMN,
                    TokenDataFactory.TARGET_COLUMN,
                ],
                write_fields=sentences_generated == 0,
            )

            sentences_generated += len(transformed_data_points)

        dataset_config = {
            "filepath": str(self.train_file_location),
            "error_file": str(self.errored_file_location),
            "task": "TOKEN_CLASSIFICATION",
            "input_feature": TokenDataFactory.SOURCE_COLUMN,
            "target_feature": TokenDataFactory.TARGET_COLUMN,
            "target_labels": tags,
            "tag_values": complete_tag_examples,
            "num_samples": sentences_generated,
        }
        save_dict(self.config_file_location, **dataset_config)

        return dataset_config

    def fill_and_transform(
        self, allowed_tags: List[str], template: str, tag_values: Dict[str, List[str]]
    ):
        words = template.split()
        if not words:
            return

        source = []
        target = []

        for word in words:
            match = re.search(r"\[(.*?)\]", word)
            if match:
                # word is a tag
                word_tag = match.group(1)
                assert word_tag in allowed_tags

                word_tag_value = random.choice(tag_values[word_tag])
                source.append(word_tag_value)

                """
                Extending the [TAG] to match the source text

                    For example:
                        template = '[NAME] reserved the hall for reunion'
                        word_tag = [NAME]
                        word_tag_value = Jessica vega

                    Expected:
                        source = 'Jessica vega reserved the hall for reunion'
                        target = 'NAME NAME O O O O O'
                """
                target.extend([word_tag] * len(word_tag_value.split(" ")))
            else:
                source.append(word)
                target.append("O")

        return {
            TokenDataFactory.SOURCE_COLUMN: " ".join(source),
            TokenDataFactory.TARGET_COLUMN: " ".join(target),
        }
