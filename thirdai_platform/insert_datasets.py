import glob
import json
import os
from shutil import copytree

from dotenv import load_dotenv

load_dotenv()

from database import schema
from database.session import get_session

filenames = glob.glob(
    "/share/data/dataset_inventory/token_classification/**/*data.json"
)

# Adding entry to DB
session = next(get_session())
for file in filenames:
    with open(file, "r") as f:
        data = json.load(f)
        if data["task"].endswith("_classification"):
            data["task"] = data["task"][: -len("_classification")]

        entry = schema.Catalog(
            id=data["id"],
            name=data["name"] if data["name"] else "unnamed_data",
            task=data["task"],
            target_labels=data["target_labels"],
            num_generated_samples=data["num_generated_samples"],
        )
        session.add(entry)
session.commit()

# Copying files
copytree(
    "/share/data/dataset_inventory/token_classification",
    os.path.join(os.getenv("SHARE_DIR"), "datasets"),
    dirs_exist_ok=True,
)
