import random
from typing import Dict, List, Optional

from data_factory_interface import DataFactory
from platform_common.utils import save_dict
from prompt_resources.text_prompts import datagen_prompt
from tqdm import tqdm
from utils import shuffle_and_filter, train_test_split, write_to_csv
from variables import Entity


class TextDataFactory(DataFactory):
    SOURCE_COLUMN = "text"
    TARGET_COLUMN = "label"

    def __init__(self):
        super().__init__()

    def collect_arguments(
        self,
        task_prompt: str,
        target_labels: List[Entity],
        sentence_to_generate_per_target_label: int,
        user_vocab: Optional[List[str]] = None,
        user_prompts: Optional[List[str]] = None,
        vocab_per_sentence: int = 4,
    ):
        extended_tag_description = self.get_extended_description(entities=target_labels)

        arguments = []
        for target_label in target_labels:
            for current_sentence_idx in range(
                0, sentence_to_generate_per_target_label, self.generate_at_a_time
            ):
                samples_to_generate = min(
                    self.generate_at_a_time,
                    sentence_to_generate_per_target_label - current_sentence_idx,
                )
                random_vocab = (
                    user_vocab if user_vocab is not None else []
                ) + self.get_random_vocab(k=vocab_per_sentence * samples_to_generate)

                label_examples = "\n".join(
                    random.sample(
                        target_label.examples,
                        min(2, len(target_label.examples)),
                    )
                )

                min_sample_len = random.randint(10, 20)
                offset = random.randint(5, 20)

                prompt = datagen_prompt.format(
                    task_prompt=task_prompt,
                    samples_to_generate=samples_to_generate,
                    label_name=target_label.name,
                    label_description=f"{target_label.description}. {extended_tag_description[target_label.name]}",
                    examples=label_examples,
                    user_prompts=(
                        ("\n".join(user_prompts) + "\n\n") if user_prompts else ""
                    ),
                    random_prompts="\n".join(self.get_random_prompts()),
                    random_vocab=str(random_vocab),
                    min_sample_len=min_sample_len,
                    max_sample_len=min_sample_len + offset,
                )
                arguments.append(
                    {"prompt": prompt, "kwargs": {"target_label": target_label.name}}
                )
        return arguments

    def generate_data(
        self,
        task_prompt: str,
        samples_per_label: int,
        target_labels: List[Entity],
        user_vocab: Optional[List[str]] = None,
        user_prompts: Optional[List[str]] = None,
        vocab_per_sentence: int = 4,
    ):
        total_expected_sentences = samples_per_label * len(target_labels)
        sentence_to_generate_per_target_label = (
            total_expected_sentences - self.train_sentences_generated
        ) // len(target_labels)

        prompt_tasks = self.collect_arguments(
            task_prompt=task_prompt,
            target_labels=target_labels,
            sentence_to_generate_per_target_label=sentence_to_generate_per_target_label,
            user_vocab=user_vocab,
            user_prompts=user_prompts,
            vocab_per_sentence=vocab_per_sentence,
        )

        random.shuffle(prompt_tasks)

        total_chunks = len(prompt_tasks) // self.write_chunk_size + 1
        for idx in tqdm(
            range(0, len(prompt_tasks), self.write_chunk_size),
            desc="Generating text data: ",
            total=total_chunks,
        ):
            chunk_to_process = prompt_tasks[idx : idx + self.write_chunk_size]

            data_points: List[Dict] = self.run_and_collect_results(
                tasks_prompt=chunk_to_process, parallelize=True
            )

            transformed_data_points = [
                item
                for data_point in data_points
                for item in self.fill_and_transform(
                    texts=data_point["response_text"],
                    target_label=data_point["kwargs"]["target_label"],
                )
            ]
            transformed_data_points = shuffle_and_filter(transformed_data_points)

            train_data_points, test_data_points = train_test_split(
                transformed_data_points, test_size=self.general_variables.test_size
            )

            if train_data_points:
                write_to_csv(
                    self.train_file_location,
                    train_data_points,
                    fieldnames=[
                        TextDataFactory.SOURCE_COLUMN,
                        TextDataFactory.TARGET_COLUMN,
                    ],
                    newline="",
                    encoding="utf-8",
                )

                self.train_sentences_generated += len(transformed_data_points)

            if test_data_points:
                write_to_csv(
                    self.test_file_location,
                    test_data_points,
                    fieldnames=[
                        TextDataFactory.SOURCE_COLUMN,
                        TextDataFactory.TARGET_COLUMN,
                    ],
                    newline="",
                    encoding="utf-8",
                )

                self.test_sentences_generated += len(transformed_data_points)

        dataset_config = {
            "filepath": str(self.train_file_location),
            "error_file": str(self.errored_file_location),
            "task": "TEXT_CLASSIFICATION",
            "input_feature": TextDataFactory.SOURCE_COLUMN,
            "target_feature": TextDataFactory.TARGET_COLUMN,
            "target_labels": [t.name for t in target_labels],
            "num_samples": self.train_sentences_generated,
        }
        save_dict(self.config_file_location, **dataset_config)

        return dataset_config

    def fill_and_transform(self, texts: str, target_label: str):
        return [
            {
                TextDataFactory.SOURCE_COLUMN: text,
                TextDataFactory.TARGET_COLUMN: target_label,
            }
            for text in texts.replace("\n\n", "\n").split("\n")
            if text.strip()
        ]
