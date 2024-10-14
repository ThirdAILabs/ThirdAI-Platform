import random
import traceback
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

from data_generation_job.llms import llm_classes
from data_generation_job.utils import count_csv_lines
from data_generation_job.variables import Entity, GeneralVariables
from prompt_resources.common_prompts import extended_description_prompt
from prompt_resources.util_data import random_prompts, vocab
from tqdm import tqdm


class DataFactory(ABC):
    def __init__(self):
        self.general_variables: GeneralVariables = GeneralVariables.load_from_env()
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
        else:
            self.train_sentences_generated = 0

        if self.test_file_location.exists():
            self.train_sentences_generated = count_csv_lines(self.test_file_location)
        else:
            self.train_sentences_generated = 0

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
        return random.sample(population=vocab, k=k)

    def get_random_prompts(self, k: int = 1):
        return [
            ". ".join(random.sample(prompts, k=k))
            for prompts in random_prompts.values()
        ]

    # ------------------------------------------------

    def process_prompt(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ):
        texts_of = self.llm_model.completion(prompt=prompt, system_prompt=system_prompt)
        return texts_of, kwargs

    """
    Function to process the prompts parallely
    args: task_prompt: List of prompts to process, List[Dict[str, str]]
        Format of each argument:
            prompt: Generation prompt to the LLM.
            system_prompt: system prompt to the LLM.
            kwargs: It is being used to store additional info about the prompt. It is not passed to LLM and returned as it is. (visit text_data_factory to see how it is being used)
    """

    def run_and_collect_results(
        self, tasks_prompt: List[Dict[str, str]], parallelize: bool = False
    ):
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
                        with open(self.errored_file_location, mode="a") as errored_fp:
                            traceback.print_exc(file=errored_fp)
                            errored_fp.write("\n" + "=" * 100 + "\n")
        else:
            for task in tqdm(tasks_prompt, desc="Progress: ", leave=False):
                response_text, kwargs = self.process_prompt(
                    task["prompt"],
                    task.get("system_prompt"),
                    **(task.get("kwargs") or {}),
                )
                data_points.append({"response_text": response_text, "kwargs": kwargs})

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
