import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

_QUIET_LOGGERS: tuple[tuple[str, int], ...] = (
    ("engineio.client", logging.ERROR),
    ("socketio.client", logging.ERROR),
    ("httpx", logging.WARNING),
    ("google_genai.models", logging.WARNING),
)


def setup_logging(
    log_dir: str = "logs",
    retention_days: int = 30,
    level: int = logging.INFO,
    console: bool = True,
    file_logging: bool = True,
) -> Path | None:
    """Console + kunlik fayl log (har kecha yangi fayl, eskilar saqlanadi)."""
    formatter = logging.Formatter(LOG_FORMAT)
    handlers: list[logging.Handler] = []

    if console:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)

    active_log_file: Path | None = None
    if file_logging:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        active_log_file = log_path / "tgtrading.log"

        file_handler = TimedRotatingFileHandler(
            filename=active_log_file,
            when="midnight",
            interval=1,
            backupCount=retention_days,
            encoding="utf-8",
            utc=False,
        )
        file_handler.suffix = "%Y-%m-%d"
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,
    )

    for logger_name, logger_level in _QUIET_LOGGERS:
        logging.getLogger(logger_name).setLevel(logger_level)

    root = logging.getLogger(__name__)
    if active_log_file is not None:
        root.info("File logging enabled: %s (retention %d days)", active_log_file, retention_days)

    return active_log_file
