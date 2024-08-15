import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional

import networkx as nx
import yaml

from headless.configs import Config
from headless.utils import get_configs

logging.basicConfig(level=logging.INFO)


class DAGExecutor:
    def __init__(
        self, function_registry: Dict[str, Callable], global_vars: Dict[str, Any] = None
    ):
        """
        Initializes the DAGExecutor with a function registry and optional global variables.

        Parameters:
        function_registry (dict): A dictionary mapping function names to callable functions.
        global_vars (dict, optional): A dictionary of global variables to be used across all DAGs.
        """
        self.dags: Dict[str, nx.DiGraph] = {}
        self.function_registry: Dict[str, Callable] = function_registry
        self.dag_configs: Dict[str, List[Config]] = {}
        self.variables: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.outputs: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.global_vars = global_vars if global_vars else {}

    def load_dags_from_file(self, file_path: str):
        """
        Loads DAGs from a YAML configuration file.

        Parameters:
        file_path (str): Path to the YAML file containing DAG configurations.
        """
        with open(file_path, "r") as file:
            config = yaml.safe_load(file)

        global_variables = config.get("variables", {})
        global_variables.update(
            self.global_vars
        )  # Update with additional global variables

        for dag_name, dag_info in config.items():
            if dag_name == "variables":
                continue
            self.add_dag(dag_name)
            config_names = dag_info.get("config")
            if isinstance(config_names, str):
                config_names = [config_names]
            self.dag_configs[dag_name] = [
                get_configs(Config, config_name)[0] for config_name in config_names
            ]
            self.variables[dag_name] = {
                config.name: global_variables.copy()
                for config in self.dag_configs[dag_name]
            }
            self.outputs[dag_name] = {
                config.name: {} for config in self.dag_configs[dag_name]
            }
            for task_name, task_info in dag_info.items():
                if task_name == "config":
                    continue
                func_name = task_info.get("function", task_name)
                func = self.function_registry.get(func_name)
                self.add_task(
                    dag_name,
                    task_name,
                    func,
                    task_info.get("dependencies", []),
                    task_info.get("params", {}),
                )

    def add_dag(self, dag_name: str):
        """
        Adds a new DAG to the executor.

        Parameters:
        dag_name (str): Name of the DAG to add.
        """
        if dag_name not in self.dags:
            self.dags[dag_name] = nx.DiGraph()

    def add_task(
        self,
        dag_name: str,
        task_name: str,
        func: Callable,
        dependencies: Optional[List[str]] = None,
        params: Optional[Dict[str, str]] = None,
    ):
        """
        Adds a task to a specified DAG.

        Parameters:
        dag_name (str): Name of the DAG to add the task to.
        task_name (str): Name of the task.
        func (Callable): The function to execute for the task.
        dependencies (list, optional): List of task names that this task depends on.
        params (dict, optional): Dictionary of parameters for the task.
        """
        self.add_dag(dag_name)
        self.dags[dag_name].add_node(task_name, func=func, params=params)
        if dependencies:
            for dep in dependencies:
                self.dags[dag_name].add_edge(dep, task_name)

    def get_execution_order(self, dag_name: str) -> List[str]:
        """
        Returns the execution order of tasks in a DAG.

        Parameters:
        dag_name (str): Name of the DAG.

        Returns:
        list: A list of task names in the order they should be executed.

        Raises:
        Exception: If the DAG has cycles, which are not allowed.
        """
        graph = self.dags[dag_name]
        try:
            order = list(nx.topological_sort(graph))
            return order
        except nx.NetworkXUnfeasible:
            raise Exception(f"The DAG '{dag_name}' has cycles, which is not allowed.")

    def get_task_func(self, dag_name: str, task_name: str) -> Callable:
        """
        Retrieves the function associated with a task in a DAG.

        Parameters:
        dag_name (str): Name of the DAG.
        task_name (str): Name of the task.

        Returns:
        Callable: The function associated with the task.
        """
        return self.dags[dag_name].nodes[task_name]["func"]

    def get_task_params(self, dag_name: str, task_name: str) -> Dict[str, str]:
        """
        Retrieves the parameters associated with a task in a DAG.

        Parameters:
        dag_name (str): Name of the DAG.
        task_name (str): Name of the task.

        Returns:
        dict: The parameters associated with the task.
        """
        return self.dags[dag_name].nodes[task_name]["params"]

    def execute_task(self, dag_name: str, task_name: str, config_name: str = None):
        """
        Executes a specified task in a DAG.

        Parameters:
        dag_name (str): Name of the DAG.
        task_name (str): Name of the task.
        config_name (str, optional): Name of the configuration.
        """
        logging.info(
            f"Executing task '{task_name}' in DAG '{dag_name}' with config '{config_name}'"
        )
        if not config_name:
            config = self.dag_configs.get(dag_name)[0]
            config_name = config.name
            self.variables[dag_name][config_name]["config"] = config
        task_func = self.get_task_func(dag_name, task_name)
        task_params = self.get_task_params(dag_name, task_name)
        logging.info(f"Executing func {task_func} with parameter {task_params}")
        if task_func:
            inputs = {}
            for param, source in task_params.items():
                if source == "variable":
                    inputs[param] = self.variables[dag_name][config_name][param]
                elif param == "config":
                    inputs[param] = get_configs(Config, source)[0]
                elif source in self.outputs[dag_name][config_name]:
                    inputs[param] = self.outputs[dag_name][config_name][source]
                else:
                    inputs[param] = source
            self.outputs[dag_name][config_name][task_name] = task_func(inputs)
        logging.info(
            f"Finished executing task '{task_name}' in DAG '{dag_name}' with config '{config_name}', with output {self.outputs[dag_name][config_name][task_name]}."
        )

    def execute_dag_with_config(self, dag_name: str, config: Config):
        """
        Executes a specified DAG with a given configuration.

        Parameters:
        dag_name (str): Name of the DAG.
        config (Config): Configuration to use for the DAG execution.
        """
        config_name = config.name
        logging.info(
            f"Starting execution of DAG '{dag_name}' with config '{config_name}'"
        )
        self.variables[dag_name][config_name]["config"] = config
        graph = self.dags[dag_name].copy()
        in_degrees = dict(graph.in_degree())

        futures = {}
        with ThreadPoolExecutor() as executor:
            for task_name in graph.nodes:
                if in_degrees[task_name] == 0:
                    futures[
                        executor.submit(
                            self.execute_task, dag_name, task_name, config_name
                        )
                    ] = (dag_name, task_name, config_name)

            while futures:
                for future in as_completed(futures):
                    dag_name, task_name, config_name = futures.pop(future)
                    try:
                        future.result()
                    except Exception as exc:
                        logging.error(
                            f"Task '{task_name}' in DAG '{dag_name}' generated an exception: {exc} for config {config_name}",
                            exc_info=True,
                        )
                    else:
                        logging.info(
                            f"Task '{task_name}' in DAG '{dag_name}' completed successfully"
                        )

                    for succ in graph.successors(task_name):
                        in_degrees[succ] -= 1
                        if in_degrees[succ] == 0:
                            futures[
                                executor.submit(
                                    self.execute_task, dag_name, succ, config_name
                                )
                            ] = (dag_name, succ, config_name)

        logging.info(
            f"Finished execution of DAG '{dag_name}' with config '{config_name}'"
        )

    def execute_dag(self, dag_name: str):
        """
        Executes all configurations of a specified DAG.

        Parameters:
        dag_name (str): Name of the DAG.
        """
        configs = self.dag_configs.get(dag_name)
        if not configs:
            raise ValueError(f"No configurations found for DAG '{dag_name}'")
        logging.info(
            f"Starting execution of DAG '{dag_name}' with {len(configs)} configurations"
        )

        futures = []
        with ThreadPoolExecutor() as executor:
            for config in configs:
                futures.append(
                    executor.submit(self.execute_dag_with_config, dag_name, config)
                )

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    logging.error(f"Configuration generated an exception: {exc}")

        logging.info(f"Finished execution of DAG '{dag_name}' with all configurations")

    def execute_all(self):
        """
        Executes all DAGs managed by the executor, with all their configurations, in parallel.
        """
        logging.info(f"Starting execution of all DAGs")

        futures = []
        with ThreadPoolExecutor() as executor:
            for dag_name in self.dags.keys():
                configs = self.dag_configs.get(dag_name)
                if not configs:
                    raise ValueError(f"No configurations found for DAG '{dag_name}'")
                for config in configs:
                    futures.append(
                        executor.submit(self.execute_dag_with_config, dag_name, config)
                    )

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    logging.error(f"Configuration generated an exception: {exc}")

        logging.info(f"Finished execution of all DAGs")

    def set_variable(self, dag_name: str, config_name: str, name: str, value: Any):
        """
        Sets a variable to a specified value.

        Parameters:
        dag_name (str): Name of the DAG.
        config_name (str): Name of the configuration.
        name (str): Name of the variable.
        value (Any): Value to set for the variable.
        """
        logging.info(
            f"Setting variable '{name}' to '{value}' for DAG '{dag_name}' and config '{config_name}'"
        )
        self.variables[dag_name][config_name][name] = value

    def update_variables(self, new_vars: Dict[str, Any]):
        """
        Updates multiple variables with new values.

        Parameters:
        new_vars (dict): A dictionary of new variable values.
        """
        for dag_name in self.variables:
            for config_name in self.variables[dag_name]:
                logging.info(
                    f"Updating variables with '{new_vars}' for DAG '{dag_name}' and config '{config_name}'"
                )
                self.variables[dag_name][config_name].update(new_vars)
