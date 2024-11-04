import random
from abc import ABC, abstractmethod
from logging import Logger
from pathlib import Path
from typing import Dict, List, Optional

from data_generation_job.llms import llm_classes
from data_generation_job.prompt_resources.common_prompts import (
    extended_description_prompt,
)
from data_generation_job.prompt_resources.util_data import random_prompts, vocab
from data_generation_job.utils import count_csv_lines
from data_generation_job.variables import Entity, GeneralVariables
from tqdm import tqdm


class DataFactory(ABC):
    def __init__(self, logger: Logger):
        self.general_variables: GeneralVariables = GeneralVariables.load_from_env()
        self.logger = logger
        self.save_dir = Path(self.general_variables.storage_dir)
        self.llm_model = llm_classes.get(self.general_variables.llm_provider.value)(
            api_key=self.general_variables.genai_key,
            response_file=self.save_dir / "response.txt",
            record_usage_at=self.save_dir / "llm_usage.json",
        )

        self.train_dir = self.save_dir / "train"
        self.test_dir = self.save_dir / "test"
        self.train_dir.mkdir(parents=True, exist_ok=True)
        self.train_file_location = self.train_dir / "train.csv"

        if self.general_variables.test_size:
            self.test_dir.mkdir(parents=True, exist_ok=True)
            self.test_file_location = self.test_dir / "test.csv"
            self.test_sentences_generated = 0

        self.errored_file_location = self.save_dir / "traceback.err"
        self.config_file_location = self.save_dir / "config.json"
        self.generation_args_location = self.save_dir / "generation_args.json"

        # These many samples would be asked to generate from an LLM call.
        self.generate_at_a_time = 40

        # These many LLM call's reponse would be written out at a time.
        self.write_chunk_size = 10

        if self.train_file_location.exists():
            self.train_sentences_generated = count_csv_lines(self.train_file_location)
            self.logger.info(
                f"Train sentences previously generated count={self.train_sentences_generated}"
            )
        else:
            self.train_sentences_generated = 0

        if self.test_file_location.exists():
            self.test_sentences_generated = count_csv_lines(self.test_file_location)
            self.logger.info(
                f"Test sentences previously generated count={self.test_sentences_generated}"
            )
        else:
            self.test_sentences_generated = 0

    # Override this function to generate the data from LLM
    @abstractmethod
    def generate_data(self, **kwargs):
        pass

    # Override this function to transform the LLM generated data to the format that can be ingested by UDT.
    @abstractmethod
    def fill_and_transform(self, **kwargs):
        pass

    # ------------------------------------------------
    ## Function to get random vocab and prompt to improve variability and randomness in the dataset
    def get_random_vocab(self, k: int = 1):
        vocab_sample = random.sample(population=vocab, k=k)
        self.logger.debug(f"Random vocab sample={vocab_sample}")
        return vocab_sample

    def get_random_prompts(self, k: int = 1):
        prompts_sample = [
            ". ".join(random.sample(prompts, k=k))
            for prompts in random_prompts.values()
        ]
        self.logger.debug(f"Random prompts sample={prompts_sample}")
        return prompts_sample

    # ------------------------------------------------

    def process_prompt(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ):
        texts_of = self.llm_model.completion(prompt=prompt, system_prompt=system_prompt)
        return texts_of, kwargs

    def run_and_collect_results(
        self, tasks_prompt: List[Dict[str, str]], parallelize: bool = False
    ):
        """
        Function to process the prompts parallely
        args: task_prompt: List of prompts to process, List[Dict[str, str]]
            Format of each argument:
                prompt: Generation prompt to the LLM.
                system_prompt: system prompt to the LLM.
                kwargs: It is being used to store additional info about the prompt. It is not passed to LLM and returned as it is. (visit text_data_factory to see how it is being used)
        """
        self.logger.info(
            f"Running tasks parallelize={parallelize}, total_tasks={len(tasks_prompt)}"
        )
        data_points = []
        if parallelize:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor() as executor, tqdm(
                total=len(tasks_prompt), desc=f"progress: ", leave=False
            ) as pbar:
                futures = []

                # Submit arguments to the executor
                for task in tasks_prompt:
                    future = executor.submit(
                        self.process_prompt,
                        task["prompt"],
                        task.get("system_prompt"),
                        **(task.get("kwargs") or {}),
                    )
                    future.add_done_callback(lambda p: pbar.update())
                    futures.append(future)

                # Wait for all arguments to complete and handle exceptions
                for future in as_completed(futures):
                    try:
                        response_text, kwargs = future.result()
                        data_points.append(
                            {"response_text": response_text, "kwargs": kwargs}
                        )

                    except Exception as e:
                        error_message = f"Error during parallel task execution: {e}"
                        self.logger.error(
                            f"Parallel task execution error={error_message}"
                        )
                        self.write_on_errorfile(error_message)
        else:
            for task in tqdm(tasks_prompt, desc="Progress: ", leave=False):
                try:
                    response_text, kwargs = self.process_prompt(
                        task["prompt"],
                        task.get("system_prompt"),
                        **(task.get("kwargs") or {}),
                    )
                    data_points.append(
                        {"response_text": response_text, "kwargs": kwargs}
                    )
                except Exception as e:
                    error_message = f"Error during serial task execution: {e}"
                    self.logger.error(f"Serial task execution error={error_message}")
                    self.write_on_errorfile(error_message)

        return data_points

    # TODO (Gautam)
    """
    Define a function `collect_argument()` that collects all the arguments 
    """

    # common function to get the extended description of tag/label
    def get_extended_description(self, entities: List[Entity]) -> Dict[str, str]:
        return {
            entity.name: self.process_prompt(
                prompt=extended_description_prompt.format(
                    attribute_name=entity.name,
                    attribute_user_description=entity.description,
                    attribute_examples=str(
                        random.sample(entity.examples, k=min(2, len(entity.examples)))
                    ),
                )
            )[0]
            for entity in entities
        }

    # Common function to report any error during any stage of pipeline
    def write_on_errorfile(self, text: str):
        with open(self.errored_file_location, "a") as errored_fp:
            errored_fp.write("\n" + "=" * 100 + "\n")
            errored_fp.write(text)
            errored_fp.write("\n" + "=" * 100 + "\n")
