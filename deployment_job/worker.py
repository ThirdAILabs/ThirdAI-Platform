import json
import time
from datetime import datetime

from routers.model import get_model
from routers.ndb import process_ndb_task
from variables import ModelType


def update_model_with_timestamp(model_id):
    model = get_model(write_mode=True)

    model.save(model_id=model_id)

    # Update the timestamp in Redis with model_id
    timestamp = datetime.utcnow().isoformat()
    model.redis_client.set(f"model_last_updated:{model_id}", timestamp)
    model.logger.info(
        f"Model (ID: {model_id}) updated and saved with timestamp: {timestamp}"
    )


def main():
    model = get_model(write_mode=True)
    redis_client = model.redis_client
    model_id = model.general_variables.model_id

    while True:
        task_ids = redis_client.smembers(f"tasks_by_model:{model_id}")

        for task_id in task_ids:
            task_id = task_id.decode()  # Decode bytes to string
            task_data = redis_client.hgetall(f"task:{task_id}")
            if task_data:
                task_data = {k.decode(): v.decode() for k, v in task_data.items()}
                for key in ["text_id_pairs", "text_pairs", "documents", "source_ids"]:
                    if key in task_data:
                        task_data[key] = json.loads(task_data[key])

                if model.general_variables.type == ModelType.NDB:
                    process_ndb_task(task_data)
                else:
                    break

        if task_ids:
            update_model_with_timestamp(model_id=model_id)

        # TODO(YASH): We need to reduce this time when we merge the ndbv2
        time.sleep(10)


if __name__ == "__main__":
    main()
