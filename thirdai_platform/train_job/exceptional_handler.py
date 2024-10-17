import functools
import sys

from platform_common.logging import get_default_logger


def exception_handler(report_method, logger):
    if logger is None:
        logger = get_default_logger()

    def decorator_exception_handler(func):
        @functools.wraps(func)
        def wrapper_exception_handler(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                print(f"Exception caught in {func.__name__}: {e}")
                logger.error(f"Exception in {func.__name__}: {e}", exc_info=True)
                instance = args[0]
                if hasattr(instance, "reporter") and hasattr(
                    instance, "general_variables"
                ):
                    reporter = instance.reporter
                    general_variables = instance.general_variables
                    report_func = getattr(reporter, report_method, None)
                    if report_func:
                        print(f"Reporting error using {report_method}")
                        if report_method == "report_shard_train_status":
                            shard_variables = instance.shard_variables
                            report_func(
                                general_variables.model_id,
                                shard_variables.shard_num,
                                "failed",
                                message=str(e),
                            )
                        else:
                            report_func(
                                general_variables.model_id,
                                "failed",
                                message=str(e),
                            )
                else:
                    print("No reporter or general_variables found in instance")

                sys.exit(0)

        return wrapper_exception_handler

    return decorator_exception_handler


def apply_exception_handler(cls):
    """
    Apply the exception handler decorator to all methods of the class.
    """
    for attr in dir(cls):
        if callable(getattr(cls, attr)) and not attr.startswith("__"):
            method = getattr(cls, attr)
            decorated_method = exception_handler(cls.report_failure_method, cls.logger)(
                method
            )
            setattr(cls, attr, decorated_method)

    # Wrap the __init__ method
    init_method = getattr(cls, "__init__", None)
    if callable(init_method):
        decorated_init = exception_handler(cls.report_failure_method, cls.logger)(
            init_method
        )
        setattr(cls, "__init__", decorated_init)

    return cls
