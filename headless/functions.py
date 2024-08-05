import logging
import os
from typing import Any, Callable, Dict

from headless.configs import Config
from headless.model import Flow
from headless.utils import create_doc_dict, extract_static_methods

logging.basicConfig(level=logging.INFO)

flow: Flow = None


def initialize_flow(base_url: str, email: str, password: str):
    """
    Initializes the Flow object with the given credentials.

    Parameters:
    base_url (str): Base URL of the API.
    email (str): Email for authentication.
    password (str): Password for authentication.
    """
    global flow
    flow = Flow(base_url=base_url, email=email, password=password)


class UDTFunctions:
    @staticmethod
    def check_udt_train(inputs: Dict[str, Any]) -> Any:
        logging.info(f"Running Udt with {inputs}")
        run_name = inputs.get("run_name")
        config: Config = inputs.get("config")

        return flow.bazaar_client.train_udt(
            model_name=f"{run_name}_{config.name}_udt_{config.sub_type}",
            supervised_docs=[
                os.path.join(config.base_path, config.unsupervised_paths[0])
            ],
            train_extra_options=UDTFunctions.build_extra_options(config),
            doc_type=config.doc_type,
        )

    @staticmethod
    def udt_deploy(inputs: Dict[str, Any]) -> Any:
        logging.info(f"inputs: {inputs}")
        model = inputs.get("model")
        run_name = inputs.get("run_name")
        config: Config = inputs.get("config")

        logging.info(
            f"Deploying the model {model.model_identifier} and id {model.model_id}"
        )

        return flow.bazaar_client.deploy_udt(
            model.model_identifier, f"{run_name}_deployment_{config.sub_type}"
        )

    def build_extra_options(config: Config) -> Dict[str, Any]:
        if config.sub_type == "text":
            return {
                "sub_type": config.sub_type,
                "text_column": config.query_column,
                "label_column": config.id_column,
                "allocation_memory": config.allocation_memory,
                "allocation_cores": config.allocation_cores,
                "n_target_classes": config.n_classes,
            }
        else:
            return {
                "sub_type": config.sub_type,
                "source_column": config.query_column,
                "target_column": config.id_column,
                "allocation_memory": config.allocation_memory,
                "allocation_cores": config.allocation_cores,
                "target_labels": config.target_labels,
            }


class CommonFunctions:
    @staticmethod
    def undeploy(inputs: Dict[str, Any]):
        """
        Stops a deployment.

        Parameters:
        inputs (dict): Dictionary containing input parameters.
        """
        logging.info(f"inputs: {inputs}")
        deployment = inputs.get("deployment")

        logging.info(f"stopping the deployment for {deployment.deployment_identifier}")

        flow.bazaar_client.undeploy(deployment)

    @staticmethod
    def check_search(inputs: Dict[str, Any]):
        logging.info(f"inputs: {inputs}")
        deployment = inputs.get("deployment")

        logging.info(f"checking the deployment for {deployment.deployment_identifier}")

        logging.info("Searching the deployment")
        return deployment.search(
            query="Can autism and down syndrome be in conjunction",
            top_k=5,
        )

    @staticmethod
    def await_deploy(inputs: Dict[str, Any]):
        """
        Awaits the completion of model deployment.

        Parameters:
        inputs (dict): Dictionary containing input parameters.
        """
        logging.info(f"inputs: {inputs}")
        deployment = inputs.get("deployment")
        logging.info(
            f"Waiting for Deployment to finish for deployment {deployment.deployment_identifier}"
        )
        flow.bazaar_client.await_deploy(deployment)

    @staticmethod
    def await_train(inputs: Dict[str, Any]):
        """
        Awaits the completion of model training.

        Parameters:
        inputs (dict): Dictionary containing input parameters.
        """
        logging.info(f"inputs: {inputs}")
        model = inputs.get("model")
        logging.info(
            f"Waiting for training to finish for model {model.model_identifier} and id {model.model_id}"
        )
        flow.bazaar_client.await_train(model)


class NDBFunctions:
    @staticmethod
    def check_deployment_ndb(inputs: Dict[str, Any]):
        """
        Checks the status and functionality of a deployment.

        Parameters:
        inputs (dict): Dictionary containing input parameters.
        """
        logging.info(f"inputs: {inputs}")
        deployment = inputs.get("deployment")
        config: Config = inputs.get("config")
        results = inputs.get("results")

        query_text = results["query_text"]
        references = results["references"]

        best_answer = references[4]
        good_answer = references[2]

        logging.info("Associating the model")
        deployment.associate(
            [
                {"source": "authors", "target": "contributors"},
                {"source": "paper", "target": "document"},
            ]
        )

        logging.info(f"upvoting the model")
        deployment.upvote(
            [
                {"query_text": query_text, "reference_id": best_answer["id"]},
                {"query_text": query_text, "reference_id": good_answer["id"]},
            ]
        )

        logging.info(f"inserting the docs to the model")
        deployment.insert(
            [
                create_doc_dict(
                    os.path.join(
                        (
                            config.base_path
                            if config.doc_type != "nfs"
                            else config.base_path
                        ),
                        file,
                    ),
                    config.doc_type,
                )
                for file in config.insert_paths
            ],
        )

        logging.info("Checking the sources")
        deployment.sources()

        logging.info("Ovveriding the model")
        deployment.save_model(override=True)

    @staticmethod
    def check_unsupervised(inputs: Dict[str, Any]) -> Any:
        logging.info(f"Running unsupervised with {inputs}")
        sharded = inputs.get("sharded")
        run_name = inputs.get("run_name")
        config: Config = inputs.get("config")
        base_model = inputs.get("base_model", None)
        file_num = inputs.get("file_num", 0)
        test = inputs.get("test", False)

        base_model_identifier = base_model.model_identifier if base_model else None

        type = "single" if not sharded else "multiple"
        return flow.train(
            model_name=f"{run_name}_{config.name}_{type}_unsupervised",
            unsupervised_docs=[
                os.path.join(config.base_path, config.unsupervised_paths[file_num])
            ],
            extra_options=NDBFunctions.build_extra_options(config, sharded),
            doc_type=config.doc_type,
            nfs_base_path=config.nfs_original_base_path,
            base_model_identifier=base_model_identifier,
            test_doc=(
                os.path.join(config.base_path, config.test_paths[0]) if test else None
            ),
        )

    @staticmethod
    def check_unsupervised_supervised(inputs: Dict[str, Any]) -> Any:
        logging.info(f"Running unsupervised supervised with {inputs}")
        sharded = inputs.get("sharded")
        run_name = inputs.get("run_name")
        config: Config = inputs.get("config")
        base_model = inputs.get("base_model", None)
        file_num = inputs.get("file_num", 0)
        test = inputs.get("test", False)

        base_model_identifier = base_model.model_identifier if base_model else None

        type = "single" if not sharded else "multiple"
        return flow.train(
            model_name=f"{run_name}_{config.name}_{type}_unsupervised_supervised",
            unsupervised_docs=[
                os.path.join(config.base_path, config.unsupervised_paths[file_num])
            ],
            supervised_docs=[
                (
                    os.path.join(config.base_path, config.supervised_paths[file_num]),
                    os.path.join(config.base_path, config.unsupervised_paths[file_num]),
                )
            ],
            extra_options=NDBFunctions.build_extra_options(config, sharded),
            doc_type=config.doc_type,
            nfs_base_path=config.nfs_original_base_path,
            base_model_identifier=base_model_identifier,
            test_doc=(
                os.path.join(config.base_path, config.test_paths[0]) if test else None
            ),
        )

    @staticmethod
    def deploy_ndb(inputs: Dict[str, Any]) -> Any:
        logging.info(f"inputs: {inputs}")
        model = inputs.get("model")
        run_name = inputs.get("run_name")

        logging.info(
            f"Deploying the model {model.model_identifier} and id {model.model_id}"
        )

        return flow.bazaar_client.deploy(
            model.model_identifier, f"{run_name}_deployment"
        )

    def build_extra_options(config: Config, sharded: bool = False) -> Dict[str, Any]:
        """
        Builds a dictionary of extra options for training.

        Parameters:
        config (Config): Configuration object containing various settings.
        sharded (bool, optional): Whether to use sharded training.

        Returns:
        dict[str, Any]: Dictionary of extra training options.
        """
        return {
            "model_cores": config.model_cores,
            "model_memory": config.model_memory,
            "csv_id_column": config.id_column,
            "csv_strong_columns": config.strong_columns,
            "csv_weak_columns": config.weak_columns,
            "csv_reference_columns": config.reference_columns,
            "fhr": config.input_dim,
            "embedding_dim": config.hidden_dim,
            "output_dim": config.output_dim,
            "csv_query_column": config.query_column,
            "csv_id_delimiter": config.id_delimiter,
            "num_models_per_shard": 2 if sharded else 1,
            "num_shards": 2 if sharded else 1,
            "allocation_memory": config.allocation_memory,
            "unsupervised_epochs": config.epochs,
            "supervised_epochs": config.epochs,
            "retriever": config.retriever,
            "checkpoint_interval": config.checkpoint_interval,
        }


class AdminFunctions:
    @staticmethod
    def add_new_users(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        try:
            flow.bazaar_client.signup(
                email="test_global_admin@mail.com",
                password="password",
                username="test_global_admin",
            )
        except Exception as e:
            pass

        try:
            flow.bazaar_client.signup(
                email="test_team_admin@mail.com",
                password="password",
                username="test_team_admin",
            )
        except Exception as e:
            pass

        try:
            flow.bazaar_client.signup(
                email="test_team_member@mail.com",
                password="password",
                username="test_team_member",
            )
        except Exception as e:
            pass

        flow.bazaar_client.login(
            email="admin@mail.com",
            password="password",
        )

    @staticmethod
    def test_add_global_admin(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        response = flow.bazaar_client.add_global_admin(inputs.get("email"))
        logging.info(
            f"Test Add Admin: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )

    @staticmethod
    def test_delete_user(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        response = flow.bazaar_client.delete_user(inputs.get("email"))
        logging.info(
            f"Test Delete User: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )

    @staticmethod
    def test_add_key(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        response = flow.bazaar_client.add_secret_key(
            inputs.get("key"), inputs.get("value")
        )
        logging.info(
            f"Add Secret Key: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )

    @staticmethod
    def test_get_key(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        response = flow.bazaar_client.get_secret_key(inputs.get("key"))
        logging.info(
            f"Get Secret Key: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )

    @staticmethod
    def test_create_team(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        response = flow.bazaar_client.create_team(inputs.get("name"))
        logging.info(
            f"Create Team: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )

    @staticmethod
    def test_add_user_to_team(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        response = flow.bazaar_client.add_user_to_team(
            inputs.get("user_email"), inputs.get("team_name")
        )
        logging.info(
            f"Add User to Team: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )

    @staticmethod
    def test_assign_team_admin(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        response = flow.bazaar_client.assign_team_admin(
            inputs.get("user_email"), inputs.get("team_name")
        )
        logging.info(
            f"Assign Team Admin: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )

    @staticmethod
    def test_delete_team(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        response = flow.bazaar_client.delete_team(inputs.get("team_name"))
        logging.info(
            f"Delete Team: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )

    @staticmethod
    def test_delete_team_admin(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        response = flow.bazaar_client.delete_user(inputs.get("email"))
        logging.info(
            f"Test Delete User: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )

    @staticmethod
    def test_delete_team_member(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        response = flow.bazaar_client.delete_user(inputs.get("email"))
        logging.info(
            f"Test Delete User: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )


functions_registry: Dict[str, Callable] = {
    **extract_static_methods(CommonFunctions),
    **extract_static_methods(NDBFunctions),
    **extract_static_methods(UDTFunctions),
    **extract_static_methods(AdminFunctions),
}
