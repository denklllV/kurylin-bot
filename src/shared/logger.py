# START OF FILE: src/shared/logger.py

import logging
import sys

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    '%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s'
)
handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(handler)

# END OF FILE: src/shared/logger.py