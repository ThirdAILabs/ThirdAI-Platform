# README: Writing and Executing Your Own DAG

## Introduction

This guide will help you create and execute Directed Acyclic Graphs (DAGs) for orchestrating tasks using a YAML configuration.

### Sample data
The sample data paths provided in the configurations can be found at https://github.com/ThirdAILabs/Services-data/tree/main/data/platform. You can use these files directly for testing, or you can use your own configurations and paths.

Set the environment variable `SHARE_DIR` to a specific folder path. The script will download data and store it in that folder, utilizing the `SHARE_DIR` path for its operations.

## Writing Your Own DAG

1. **Create a YAML File**: Define your DAGs, tasks, dependencies, and parameters.

### Structure

Each DAG consists of multiple tasks. Each task can have dependencies (tasks that must be completed before it can run) and parameters.

### Example YAML File

```yaml
DAG1:
  config: [text, token]
  check_unsupervised:
    dependencies: []
    params:
      sharded: variable
      run_name: variable
      config: variable

  await_train:
    dependencies: [check_unsupervised]
    params:
      model: check_unsupervised

  deploy:
    dependencies: [await_train]
    params:
      model: check_unsupervised
      run_name: variable

  await_deploy:
    dependencies: [deploy]
    params:
      deployment: deploy

DAG2:
  check_unsupervised_supervised:
    dependencies: []
    params:
      sharded: variable
      run_name: variable
      config: variable

  await_train:
    dependencies: [check_unsupervised_supervised]
    params:
      model: check_unsupervised_supervised
```

### Key Elements
- DAG_NAME: The name of the DAG.
- Config: List of configs on which this dag will run (All the configs will run parallely.)
- TASK_NAME: The name of the task within the DAG ( these must be the functions in the function_registry)
- dependencies: A list of tasks that must be completed before this task.
- params: Parameters required by the task. These can be variables or outputs from other tasks or raw values too.


## Executing the DAG

Run the DAG using the command-line interface with the provided script.

### Command-Line Arguments

- `--dag-file`: Path to the DAG YAML file (default: `dag_config.yaml`).
- `--dag`: Name of the DAG to run.
- `--task`: Name of the individual task to run within the DAG.
- `--all`: Run all DAGs.
- `--run-name`: Name of the run (required).
- `--sharded`: Run sharded training.

### Example Commands

- **Run All DAGs**:
  It will run all dags parallely.
  ```sh
  python your_script.py --dag-file path/to/dag_config.yaml --all --run-name your_run_name
  ```

- **Run a Specific DAG**:
  ```sh
  python your_script.py --dag-file path/to/dag_config.yaml --dag DAG1 --run-name your_run_name
  ```

- **Run a Specific Task in a DAG**:
  ```sh
  python your_script.py --dag-file path/to/dag_config.yaml --dag DAG1 --task check_unsupervised --run-name your_run_name
  ```


## Conclusion
This guide provides a concise overview of executing DAG configurations. Follow these steps to run your workflows and automate their execution effectively.