import json


def save_dict(write_to: str, **kwargs):
    with open(write_to, "w") as fp:
        json.dump(kwargs, fp, indent=4)


def load_dict(path: str):
    with open(path, "r") as fp:
        return json.load(fp)
