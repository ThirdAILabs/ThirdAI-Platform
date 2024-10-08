import logging
import os
import time
from typing import Any, Callable, Dict

from requests.exceptions import HTTPError

from headless.configs import Config
from headless.model import Flow
from headless.utils import extract_static_methods

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
        dag_name = inputs.get("dag_name")

        return flow.bazaar_client.train_udt(
            model_name=f"{run_name}_{dag_name}_{config.name}_udt_{config.sub_type}",
            supervised_docs=[
                os.path.join(config.base_path, config.unsupervised_paths[0])
            ],
            model_options=UDTFunctions.build_model_options(config),
            job_options=UDTFunctions.build_job_options(config),
            doc_type=config.doc_type,
        )

    @staticmethod
    def check_udt_train_with_datagen(inputs: Dict[str, Any]) -> Any:
        logging.info(f"Running Udt with datagen with {inputs}")
        run_name = inputs.get("run_name")
        config: Config = inputs.get("config")
        dag_name = inputs.get("dag_name")

        return flow.bazaar_client.train_udt_with_datagen(
            model_name=f"{run_name}_{dag_name}_{config.name}_udt_with_datagen_{config.sub_type}",
            examples=config.examples,
            task_prompt=config.task_prompt,
            sub_type=config.sub_type,
            datagen_job_options=UDTFunctions.build_job_options(config),
            train_job_options=UDTFunctions.build_job_options(config),
        )

    @staticmethod
    def check_predict(inputs: Dict[str, Any]):
        logging.info(f"inputs: {inputs}")
        deployment = inputs.get("deployment")

        logging.info(f"checking the deployment for {deployment.model_identifier}")

        logging.info("Calling predict on the deployment")
        return deployment.predict(
            text="Can autism and down syndrome be in conjunction",
            top_k=5,
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
            model.model_identifier,
            f"udt_{model.model_identifier}_deployment_{run_name}",
        )

    def build_model_options(config: Config) -> Dict[str, Any]:
        if config.sub_type == "text":
            return {
                "udt_options": {
                    "udt_sub_type": "text",
                    "text_column": config.query_column,
                    "label_column": config.id_column,
                    "n_target_classes": config.n_classes,
                }
            }
        return {
            "udt_options": {
                "udt_sub_type": "token",
                "target_labels": config.target_labels,
                "source_column": config.query_column,
                "target_column": config.id_column,
            }
        }

    def build_job_options(config: Config) -> Dict[str, Any]:
        return {
            "allocation_memory": config.allocation_memory,
            "allocation_cores": config.allocation_cores,
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

        logging.info(f"stopping the deployment for {deployment.model_identifier}")

        flow.bazaar_client.undeploy(deployment)

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
            f"Waiting for Deployment to finish for deployment {deployment.model_identifier}"
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

    @staticmethod
    def delete_model(inputs: Dict[str, Any]):
        """
        Delete the given model
        """

        logging.info(f"Deleting the model with inputs: {inputs}")
        model = inputs.get("model")
        flow.bazaar_client.delete(model_identifier=model.model_identifier)
        logging.info(f"Deleted the model {model.model_identifier}")

    @staticmethod
    def get_logs(inputs: Dict[str, Any]):
        """
        Get the logs for the model.
        """
        logging.info(f"Getting the model logs with inputs: {inputs}")
        model = inputs.get("model")
        flow.bazaar_client.logs(model)
        logging.info(f"Got the logs for {model.model_identifier}")
        flow.bazaar_client.cleanup_cache()
        logging.info(f"Bazaar cache is cleaned")


class NDBFunctions:
    @staticmethod
    def check_search(inputs: Dict[str, Any]):
        logging.info(f"inputs: {inputs}")
        deployment = inputs.get("deployment")

        logging.info(f"checking the deployment for {deployment.model_identifier}")

        logging.info("Searching the deployment")
        return deployment.search(
            query="Can autism and down syndrome be in conjunction",
            top_k=5,
        )

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
        generation = inputs.get("generation", False)
        on_prem = inputs.get("on_prem")

        query_text = results["query_text"]
        references = results["references"]

        best_answer = references[4]
        good_answer = references[2]

        logging.info("Associating the model")
        associate_response = deployment.associate(
            [
                {"source": "authors", "target": "contributors"},
                {"source": "paper", "target": "document"},
            ]
        )

        assert associate_response.status_code == 200

        logging.info(f"upvoting the model")
        upvote_response = deployment.upvote(
            [
                {"query_text": query_text, "reference_id": best_answer["id"]},
                {"query_text": query_text, "reference_id": good_answer["id"]},
            ]
        )

        assert upvote_response.status_code == 200

        logging.info(f"inserting the docs to the model")
        insert_response = deployment.insert(
            [
                {
                    "path": os.path.join(config.base_path, file),
                    "location": config.doc_type,
                }
                for file in config.insert_paths
            ],
        )
        assert insert_response.status_code == 200

        logging.info("Checking the sources")
        deployment.sources()

        logging.info("Ovveriding the model")
        deployment.save_model(override=True)

        llm_client = deployment.llm_client()

        if generation:
            api_key = os.getenv("GENAI_KEY", None)
            if api_key:
                generated_answer = llm_client.generate(
                    query=best_answer["text"],
                    api_key=api_key,
                    provider="openai",
                    use_cache=True,
                )
                logging.info(f"Openai generated answer: {generated_answer}")
                if not generated_answer:
                    raise Exception(f"Openai answer is not generated")

                deployment.update_chat_settings(provider="openai")

                chat_response = deployment.chat(
                    user_input=best_answer["text"],
                    session_id=deployment.model_id,
                    provider="openai",
                )

                logging.info(f"OpenAI Chat response {chat_response}")

                chat_history = deployment.get_chat_history(
                    session_id=deployment.model_id
                )

                logging.info(f"OpenAI Chat history {chat_history}")

            if on_prem:
                flow.bazaar_client.start_on_prem(autoscaling_enabled=False)
                # waiting for our on-prem to start and trafeik to discover the service
                time.sleep(45)
                generated_answer = llm_client.generate(
                    query=best_answer["text"],
                    api_key="no key",
                    provider="on-prem",
                    use_cache=False,
                )
                logging.info(f"on-prem generated answer: {generated_answer}")
                if not generated_answer:
                    raise Exception(f"On prem answer is not generated")

                deployment.update_chat_settings(provider="on-prem")

                deployment.chat(
                    user_input=best_answer["text"],
                    session_id=deployment.model_id,
                    provider="on-prem",
                )

                logging.info(f"On prem Chat response {chat_response}")

                chat_history = deployment.get_chat_history(
                    session_id=deployment.model_id
                )

                logging.info(f"On prem Chat history {chat_history}")

    @staticmethod
    def check_unsupervised(inputs: Dict[str, Any]) -> Any:
        logging.info(f"Running unsupervised with {inputs}")
        run_name = inputs.get("run_name")
        config: Config = inputs.get("config")
        base_model = inputs.get("base_model", None)
        file_num = inputs.get("file_num", 0)
        test = inputs.get("test", False)
        dag_name = inputs.get("dag_name")

        base_model_identifier = base_model.model_identifier if base_model else None

        unsup_docs = [
            os.path.join(config.base_path, config.unsupervised_paths[file_num])
        ]
        return flow.train(
            model_name=f"{run_name}_{dag_name}_{config.name}_unsupervised",
            unsupervised_docs=unsup_docs,
            model_options=NDBFunctions.build_model_options(config),
            doc_type=config.doc_type,
            nfs_base_path=config.nfs_original_base_path,
            base_model_identifier=base_model_identifier,
            test_doc=(
                os.path.join(config.base_path, config.test_paths[0]) if test else None
            ),
            doc_options={
                doc: NDBFunctions.build_doc_options(config) for doc in unsup_docs
            },
            job_options=NDBFunctions.build_job_options(config),
        )

    @staticmethod
    def check_supervised(inputs: Dict[str, Any]) -> Any:
        logging.info(f"Running supervised with {inputs}")
        run_name = inputs.get("run_name")
        config: Config = inputs.get("config")
        base_model = inputs.get("base_model", None)
        file_num = inputs.get("file_num", 0)
        test = inputs.get("test", False)
        dag_name = inputs.get("dag_name")

        base_model_identifier = base_model.model_identifier if base_model else None

        sup_docs = [
            (
                os.path.join(config.base_path, config.supervised_paths[file_num]),
                os.path.join(config.base_path, config.unsupervised_paths[file_num]),
            )
        ]

        return flow.train(
            model_name=f"{run_name}_{dag_name}_{config.name}_supervised",
            supervised_docs=sup_docs,
            model_options=NDBFunctions.build_model_options(config),
            doc_type=config.doc_type,
            nfs_base_path=config.nfs_original_base_path,
            base_model_identifier=base_model_identifier,
            test_doc=(
                os.path.join(config.base_path, config.test_paths[0]) if test else None
            ),
            doc_options={
                doc: NDBFunctions.build_doc_options(config)
                for doc in [sup_docs[0][0], sup_docs[0][1]]
            },
            job_options=NDBFunctions.build_job_options(config),
        )

    @staticmethod
    def check_unsupervised_supervised(inputs: Dict[str, Any]) -> Any:
        logging.info(f"Running unsupervised supervised with {inputs}")
        run_name = inputs.get("run_name")
        config: Config = inputs.get("config")
        base_model = inputs.get("base_model", None)
        file_num = inputs.get("file_num", 0)
        test = inputs.get("test", False)
        dag_name = inputs.get("dag_name")

        base_model_identifier = base_model.model_identifier if base_model else None

        unsup_docs = [
            os.path.join(config.base_path, config.unsupervised_paths[file_num])
        ]
        sup_docs = [
            (
                os.path.join(config.base_path, config.supervised_paths[file_num]),
                os.path.join(config.base_path, config.unsupervised_paths[file_num]),
            )
        ]
        return flow.train(
            model_name=f"{run_name}_{dag_name}_{config.name}_unsupervised_supervised",
            unsupervised_docs=unsup_docs,
            supervised_docs=sup_docs,
            model_options=NDBFunctions.build_model_options(config),
            doc_type=config.doc_type,
            nfs_base_path=config.nfs_original_base_path,
            base_model_identifier=base_model_identifier,
            test_doc=(
                os.path.join(config.base_path, config.test_paths[0]) if test else None
            ),
            doc_options={
                doc: NDBFunctions.build_doc_options(config)
                for doc in unsup_docs + [sup_docs[0][0]]
            },
            job_options=NDBFunctions.build_job_options(config),
        )

    @staticmethod
    def deploy_ndb(inputs: Dict[str, Any]) -> Any:
        logging.info(f"inputs: {inputs}")
        model = inputs.get("model")

        logging.info(
            f"Deploying the model {model.model_identifier} and id {model.model_id}"
        )

        return flow.bazaar_client.deploy(model.model_identifier)

    def build_model_options(config: Config) -> Dict[str, Any]:
        if config.ndb_version == "v1":
            if config.retriever == "mach":
                mach_options = {
                    "fhr": config.input_dim,
                    "embedding_dim": config.hidden_dim,
                    "output_dim": config.output_dim,
                    "unsupervised_epochs": config.epochs,
                    "supervised_epochs": config.epochs,
                }
            else:
                mach_options = None
            return {
                "ndb_options": {
                    "ndb_sub_type": "v1",
                    "retriever": config.retriever,
                    "mach_options": mach_options,
                    "checkpoint_interval": config.checkpoint_interval,
                }
            }
        elif config.ndb_version == "v2":
            return {"ndb_options": {"ndb_sub_type": "v2"}}
        else:
            raise ValueError(f"Invalid ndb version '{config.ndb_version}'")

    def build_doc_options(config: Config) -> Dict[str, Any]:
        return {
            "csv_id_column": config.id_column,
            "csv_strong_columns": config.strong_columns,
            "csv_weak_columns": config.weak_columns,
            "csv_reference_columns": config.reference_columns,
            "csv_query_column": config.query_column,
            "csv_id_delimiter": config.id_delimiter,
        }

    def build_job_options(config: Config) -> Dict[str, Any]:
        return {
            "allocation_memory": config.allocation_memory,
        }


class GlobalAdminFunctions:
    @staticmethod
    def add_new_users(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        try:
            flow.bazaar_client.sign_up(
                email="ga_test_global_admin@mail.com",
                password="password",
                username="ga_test_global_admin",
            )
        except Exception as e:
            pass

        try:
            flow.bazaar_client.sign_up(
                email="ga_test_team_admin@mail.com",
                password="password",
                username="ga_test_team_admin",
            )
        except Exception as e:
            pass

        try:
            flow.bazaar_client.sign_up(
                email="ga_test_team_member@mail.com",
                password="password",
                username="ga_test_team_member",
            )
        except Exception as e:
            pass

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
        print(response)

        return response

    @staticmethod
    def test_add_user_to_team(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        response = flow.bazaar_client.add_user_to_team(
            inputs.get("user_email"), inputs.get("team_id")
        )
        logging.info(
            f"Add User to Team: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )

    @staticmethod
    def test_assign_team_admin(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        response = flow.bazaar_client.assign_team_admin(
            inputs.get("user_email"), inputs.get("team_id")
        )
        logging.info(
            f"Assign Team Admin: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )

    @staticmethod
    def test_delete_team(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        response = flow.bazaar_client.delete_team(inputs.get("team_id"))
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


class TeamAdminFunctions:
    @staticmethod
    def ta_setup(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        try:
            flow.bazaar_client.sign_up(
                email="ta_team_admin@mail.com",
                password="password",
                username="ta_team_admin",
            )
        except Exception as e:
            logging.error(f"Failed to sign_up another team admin: {e}")

        try:
            flow.bazaar_client.sign_up(
                email="ta_another_team_admin@mail.com",
                password="password",
                username="ta_another_team_admin",
            )
        except Exception as e:
            logging.error(f"Failed to sign_up another team admin: {e}")

        try:
            flow.bazaar_client.sign_up(
                email="ta_test_team_member@mail.com",
                password="password",
                username="ta_test_team_member",
            )
        except Exception as e:
            logging.error(f"Failed to sign_up another team member: {e}")

        response = flow.bazaar_client.add_secret_key(
            inputs.get("key"), inputs.get("value")
        )

    @staticmethod
    def test_ta_add_user_to_team(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        flow.bazaar_client.log_in(
            email="ta_team_admin@mail.com",
            password="password",
        )

        response = flow.bazaar_client.add_user_to_team(
            inputs.get("user_email"), inputs.get("team_id")
        )
        logging.info(
            f"Add User to Team: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )

    @staticmethod
    def test_ta_assign_team_admin(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")

        response = flow.bazaar_client.assign_team_admin(
            inputs.get("user_email"), inputs.get("team_id")
        )
        logging.info(
            f"Assign Team Admin: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )

    @staticmethod
    def test_ta_delete_team_member(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        try:
            logging.info(
                "Login Instance: %s", flow.bazaar_client._login_instance.username
            )

            response = flow.bazaar_client.remove_user_from_team(
                inputs.get("email"), inputs.get("team_id")
            )
            logging.info(
                f"Test Delete Team Member: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
            )
        except HTTPError as e:
            if e.response.status_code == 403:
                logging.info("Passes")
            else:
                raise

    @staticmethod
    def test_ta_add_key(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")
        try:
            logging.info(
                "Login Instance: %s", flow.bazaar_client._login_instance.username
            )

            response = flow.bazaar_client.add_secret_key(
                inputs.get("key"), inputs.get("value")
            )
            logging.info(
                f"Add Secret Key: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
            )
        except HTTPError as e:
            if e.response.status_code == 403:
                logging.info("Passes")
            else:
                raise

    @staticmethod
    def test_ta_get_key(inputs: Dict[str, str]):
        logging.info(f"inputs: {inputs}")

        response = flow.bazaar_client.get_secret_key(inputs.get("key"))
        logging.info(
            f"Get Secret Key: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
        )

    @staticmethod
    def ta_cleanup(inputs: Dict[str, str]):
        logging.info("Starting cleanup process.")
        team_id = inputs.get("team_id")

        user_emails = [
            "ta_team_admin@mail.com",
            "ta_another_team_admin@mail.com",
            "ta_test_team_member@mail.com",
        ]

        flow.bazaar_client.log_in(flow._global_email, flow._global_password)

        for email in user_emails:
            try:
                response = flow.bazaar_client.delete_user(email)
                logging.info(
                    f"Delete User {email}: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
                )
            except Exception as e:
                logging.error(f"Failed to delete user {email}: {e}")

        try:
            response = flow.bazaar_client.delete_team(team_id)
            logging.info(
                f"Delete Team {team_id}: {'Passed' if response.status_code == 200 else 'Failed'} - {response.json()}"
            )
        except Exception as e:
            logging.error(f"Failed to delete team {team_id}: {e}")

        logging.info("Cleanup process completed.")


functions_registry: Dict[str, Callable] = {
    **extract_static_methods(CommonFunctions),
    **extract_static_methods(NDBFunctions),
    **extract_static_methods(UDTFunctions),
    **extract_static_methods(GlobalAdminFunctions),
    **extract_static_methods(TeamAdminFunctions),
}
