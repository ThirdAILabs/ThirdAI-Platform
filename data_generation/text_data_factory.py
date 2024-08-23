import random
from resource.text_prompts import datagen_prompt
from typing import Dict, List, Optional

from data_factory_interface import DataFactory
from tqdm import tqdm
from utils import assert_sufficient_descriptions, assert_sufficient_examples, save_dict


class TextDataFactory(DataFactory):
    SOURCE_COLUMN = "text"
    TARGET_COLUMN = "label"

    def __init__(self):
        super().__init__()

    def generate_data(
        self,
        task_prompt: str,
        samples_per_label: int,
        target_labels: List[str],
        examples: Dict[str, List[str]],
        labels_description: Dict[str, str],
        user_vocab: Optional[List[str]] = None,
        user_prompts: Optional[List[str]] = None,
        vocab_per_sentence=4,
        sentences_generated=0,  # To resume the generate function incase of midway failure. TODO(Gautam): Incorporate resuming the data_generation task
    ):
        total_expected_sentences = samples_per_label * len(target_labels)
        assert sentences_generated < total_expected_sentences

        assert_sufficient_examples(target_labels, examples)
        assert_sufficient_descriptions(target_labels, labels_description)

        prompt_tasks = []

        for target_label in target_labels:
            for current_sentence_idx in range(
                0, samples_per_label, self.generate_at_a_time
            ):
                samples_to_generate = min(
                    self.generate_at_a_time, samples_per_label - current_sentence_idx
                )
                random_vocab = self.get_random_vocab(
                    user_vocab, k=vocab_per_sentence * samples_to_generate
                )

                label_examples = "\n".join(
                    random.sample(
                        examples[target_label],
                        min(2, len(examples[target_label])),
                    )
                )

                prompt = datagen_prompt.format(
                    task_prompt=task_prompt,
                    samples_to_generate=samples_to_generate,
                    label_to_generate=target_label,
                    label_description=labels_description[target_label],
                    examples=label_examples,
                    user_prompts=(
                        ("\n".join(user_prompts) + "\n\n") if user_prompts else ""
                    ),
                    random_prompts="\n".join(self.get_random_prompts()),
                    random_vocab=str(random_vocab),
                )
                prompt_tasks.append(
                    {"prompt": prompt, "kwargs": {"target_label": target_label}}
                )

        # Shuffling
        random.shuffle(prompt_tasks)

        prompt_tasks = prompt_tasks[: total_expected_sentences - sentences_generated]

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
            # filtering to remove 'None'
            transformed_data_points = list(
                filter(lambda x: x is not None, transformed_data_points)
            )

            random.shuffle(transformed_data_points)

            self.write_on_training_file(
                transformed_data_points,
                fieldnames=[
                    TextDataFactory.SOURCE_COLUMN,
                    TextDataFactory.TARGET_COLUMN,
                ],
                write_fields=sentences_generated == 0,
                newline="",
                encoding="utf-8",
            )

            sentences_generated += len(transformed_data_points)

        dataset_config = {
            "filepath": str(self.train_file_location),
            "error_file": str(self.errored_file_location),
            "task": "TEXT_CLASSIFICATION",
            "input_feature": TextDataFactory.SOURCE_COLUMN,
            "target_feature": TextDataFactory.TARGET_COLUMN,
            "target_labels": target_labels,
            "num_samples": sentences_generated,
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
