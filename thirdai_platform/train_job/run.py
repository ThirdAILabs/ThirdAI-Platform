try:
    import logging
    import sys
    from logging import Logger
    from pathlib import Path

    import nltk
    from platform_common.logging import setup_logger

    nltk.download("punkt_tab")
    print("Downloading punkttab")

    import argparse
    import os

    import thirdai
    from platform_common.pydantic_models.training import (
        ModelType,
        NDBSubType,
        RetrieverType,
        TrainConfig,
        UDTSubType,
    )
    from train_job.models.classification_models import (
        TextClassificationModel,
        TokenClassificationModel,
    )
    from train_job.models.finetunable_retriever import FinetunableRetriever
    from train_job.models.neural_db_v2 import NeuralDBV2
    from train_job.models.single_mach import SingleMach
    from train_job.reporter import HttpReporter, Reporter
except ImportError as e:
    logging.error(f"Failed to import module: {e}")
    sys.exit(f"ImportError: {e}")


def get_model(config: TrainConfig, reporter: Reporter, logger: Logger):
    model_type = config.model_options.model_type
    logger.info(f"model type: {model_type}")

    if model_type == ModelType.NDB:
        if config.model_options.ndb_options.ndb_sub_type == NDBSubType.v1:
            retriever = config.model_options.ndb_options.retriever
            logger.info(f"NDB v1 with retriever type: {retriever}")

            if retriever == RetrieverType.finetunable_retriever:
                return FinetunableRetriever(config, reporter, logger)
            elif retriever == RetrieverType.hybrid or retriever == RetrieverType.mach:
                return SingleMach(config, reporter, logger)
            else:
                logger.error(f"Unsupported NDB retriever '{retriever.value}'")
                raise ValueError(f"Unsupported NDB retriever '{retriever.value}'")

        elif config.model_options.ndb_options.ndb_sub_type == NDBSubType.v2:
            return NeuralDBV2(config, reporter, logger)
        else:
            logger.error(
                f"Invalid NDB sub type {config.model_options.ndb_options.ndb_sub_type}"
            )
            raise ValueError(
                f"Invalid NDB sub type {config.model_options.ndb_options.ndb_sub_type}"
            )
    elif model_type == ModelType.UDT:
        udt_type = config.model_options.udt_options.udt_sub_type
        logger.info(f"UDT type: {udt_type}")

        if udt_type == UDTSubType.text:
            return TextClassificationModel(config, reporter, logger)
        elif udt_type == UDTSubType.token:
            return TokenClassificationModel(config, reporter, logger)
        else:
            logger.error(f"Unsupported UDT subtype '{udt_type.value}'")
            raise ValueError(f"Unsupported UDT subtype '{udt_type.value}'")

    logger.error(f"Unsupported model type {model_type.value}")
    raise ValueError(f"Unsupported model type {model_type.value}")


def load_config():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)

    args = parser.parse_args()

    with open(args.config) as file:
        return TrainConfig.model_validate_json(file.read())


def main():
    config: TrainConfig = load_config()

    log_dir: Path = Path(config.model_bazaar_dir) / "logs" / config.model_id

    setup_logger(log_dir=log_dir, log_prefix="train")

    logger = logging.getLogger("train")

    reporter = HttpReporter(config.model_bazaar_endpoint, logger)

    try:
        if config.license_key == "file_license":
            license_path = os.path.join(
                config.model_bazaar_dir, "license/license.serialized"
            )
            thirdai.licensing.set_path(license_path)
            logger.info(f"License activated using file path: {license_path}")
        else:
            thirdai.licensing.activate(config.license_key)
            logger.info("License activated with key")

        model = get_model(config, reporter, logger)

        model.train()
    except Exception as error:
        logger.error(f"Training failed with error: {error}")
        reporter.report_status(
            config.model_id,
            status="failed",
            message=f"Training failed with error {error}",
        )
        raise error


if __name__ == "__main__":
    main()
