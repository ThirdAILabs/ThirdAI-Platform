import csv
import os
import random
import re
from typing import Dict, List, Optional


def remove_duplicates(words: List[str]):
    seen = set()
    uniques = []
    for item in words:
        if item and not bool(re.fullmatch(r"^\s*$", item)) and item.lower() not in seen:
            seen.add(item.lower())
            uniques.append(item)

    return uniques


def shuffle_and_filter(data_points: List):
    random.shuffle(data_points)
    return list(filter(lambda x: x not in [None, [], {}, "", " "], data_points))


def write_to_csv(
    path: str,
    data_points: List[Dict[str, str]],
    fieldnames: List[str],
    newline: Optional[str] = None,
    encoding: Optional[str] = None,
):
    if os.path.exists(path):
        mode = "a"
    else:
        mode = "w"
    with open(path, mode, newline=newline, encoding=encoding) as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        if mode == "w":
            csv_writer.writeheader()
        csv_writer.writerows(data_points)


def count_csv_lines(path: str):
    with open(path, "r") as fp:
        num_lines = sum(1 for _ in csv.reader(fp)) - 1  # Excluding the header

    return num_lines


def train_test_split(data_points: List, test_size: float = 0.2, shuffle: bool = True):
    if shuffle:
        random.shuffle(data_points)

    if not test_size:
        return data_points, None

    split_index = int(len(data_points) * (1 - test_size))
    train_set, test_set = (
        data_points[:split_index],
        data_points[split_index:],
    )

    return train_set, test_set
