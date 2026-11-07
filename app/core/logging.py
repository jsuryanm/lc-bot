import sys

from loguru import logger

_configured = False


def setup_logging(retention: str = "7 days") -> None:
    """One log file per run: logs/<date>/<time>.log. Old files are deleted on startup."""
    global _configured
    if _configured:  # calling twice would write every line twice
        return
    _configured = True
    logger.remove()  # drop the default stderr sink so we control the format
    logger.add(sys.stderr, level="INFO")
    logger.add(
        "logs/{time:YYYY-MM-DD}/{time:HH-mm-ss}.log",
        level="DEBUG",
        retention=retention,
        encoding="utf-8",
    )