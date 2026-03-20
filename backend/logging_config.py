import logging
import sys
from logging.handlers import RotatingFileHandler


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
    format_string: str | None = None
) -> logging.Logger:
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"

    handlers: list[logging.Handler] = []

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(format_string))
    handlers.append(console_handler)

    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10_000_000,
            backupCount=5
        )
        file_handler.setFormatter(logging.Formatter(format_string))
        handlers.append(file_handler)

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=handlers,
        force=True
    )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    return logging.getLogger()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
