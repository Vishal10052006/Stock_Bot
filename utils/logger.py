import logging


def setup_logger():

    logger = logging.getLogger("PersonalAI")

    logger.setLevel(logging.INFO)

    if not logger.handlers:

        handler = logging.StreamHandler()

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )

        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger


logger = setup_logger()