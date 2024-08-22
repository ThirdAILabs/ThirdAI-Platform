import csv
import json
import random
import traceback
from abc import ABC, abstractmethod
from pathlib import Path
from resource.util_data import random_prompts, vocab
from typing import Dict, List, Optional

from llms import llm_classes
from tqdm import tqdm
from variables import GeneralVariables


class DataFactory(ABC):
    def __init__(self):
        self.general_variables: GeneralVariables = GeneralVariables.load_from_env()
        self.save_dir = (
            Path(self.general_variables.model_bazaar_dir)
            / self.general_variables.data_id
        )
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.llm_model = llm_classes.get(self.general_variables.llm_provider.value)(
            api_key=self.general_variables.genai_key
        )
        self.train_file_location = self.save_dir / "train.csv"
        self.errored_file_location = self.save_dir / "traceback.err"
        self.config_file_location = self.save_dir / "config.json"
        self.generation_args_location = self.save_dir / "generation_args.json"

        self.generate_at_a_time = 40
        self.write_chunk_size = 50

    @abstractmethod
    def generate_data(self, **kwargs):
        pass

    @abstractmethod
    def fill_and_transform(self, **kwargs):
        pass

    def get_random_vocab(self, user_vocab: Optional[str] = None, k: int = 1):
        vocabulary = vocab + (user_vocab if user_vocab is not None else [])
        return random.sample(population=vocabulary, k=k)

    def get_random_prompts(self, k: int = 1):
        # Don't have weighted random.choice() functionality.
        return [
            random.choices(items["prompts"], weights=items["scores"], k=k)[0]
            for items in random_prompts.values()
        ]

    def process_prompt(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ):
        texts_of = self.llm_model.completion(prompt=prompt, system_prompt=system_prompt)
        return texts_of, kwargs

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

    def write_on_training_file(
        self,
        data_points: List[Dict[str, str]],
        fieldnames: List[str],
        write_fields: bool = True,
        newline: Optional[str] = None,
        encoding: Optional[str] = None,
    ):
        try:
            with open(
                self.train_file_location, "a", newline=newline, encoding=encoding
            ) as csv_file:
                csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                if write_fields:
                    csv_writer.writeheader()
                csv_writer.writerows(data_points)
        except Exception as e:
            with open(self.errored_file_location, mode="a") as errored_fp:
                errored_fp.write(
                    "\nError while writing on train file " + "-" * 20 + "\n"
                )
                traceback.print_exc(file=errored_fp)
                errored_fp.write("\n" + "=" * 100 + "\n")
                errored_fp.write("Data-points: \n")
                errored_fp.write(str(data_points) + "\n")
                errored_fp.write("\n" + "=" * 100 + "\n")
