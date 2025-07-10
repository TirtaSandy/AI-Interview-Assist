import logging

def setup_logger():
    logger = logging.getLogger('PrivacyToolkitLogger')
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
