import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"

_logger = None


def get_logger():
    global _logger
    if _logger is not None:
        return _logger

    LOG_DIR.mkdir(exist_ok=True)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    _logger = logging.getLogger("engine_coursework")
    _logger.setLevel(logging.INFO)
    _logger.handlers.clear()
    _logger.addHandler(file_handler)
    _logger.addHandler(console_handler)
    _logger.propagate = False

    for name in ("werkzeug", "flask.app"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return _logger
