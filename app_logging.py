"""Единые настройки логирования приложения."""

import logging
import os
from datetime import datetime

MAX_LOG_LINES = 500
LOG_FILENAME = "plan_generator.log"
UPDATE_LOG_FILENAME = "update.log"
TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"


def now_timestamp() -> str:
    return datetime.now().strftime(TIMESTAMP_FMT)


def trim_text_lines(text: str, max_lines: int = MAX_LOG_LINES) -> str:
    lines = text.split("\n")
    # Последняя пустая строка после split часто «хвост» — не считаем её отдельно при сравнении лимита
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if len(lines) <= max_lines:
        return "\n".join(lines) + ("\n" if text.endswith("\n") and lines else "")
    trimmed = lines[-max_lines:]
    return "\n".join(trimmed) + "\n"


def trim_log_file(path: str, max_lines: int = MAX_LOG_LINES) -> None:
    """Оставляет в файле только последние max_lines строк."""
    try:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content:
            return
        new_content = trim_text_lines(content, max_lines)
        if new_content != content:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content if new_content.endswith("\n") else new_content + "\n")
    except OSError:
        pass


def read_log_tail(path: str, max_lines: int = MAX_LOG_LINES) -> str:
    """Читает хвост лог-файла (не больше max_lines)."""
    try:
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return trim_text_lines(content, max_lines)
    except OSError:
        return ""


class TruncatingFileHandler(logging.FileHandler):
    """FileHandler, который после записи обрезает файл до MAX_LOG_LINES."""

    def __init__(self, filename, max_lines=MAX_LOG_LINES, **kwargs):
        self.max_lines = max_lines
        kwargs.setdefault("encoding", "utf-8")
        super().__init__(filename, **kwargs)

    def emit(self, record):
        super().emit(record)
        self.flush()
        trim_log_file(self.baseFilename, self.max_lines)


def setup_app_logger(log_path: str = LOG_FILENAME) -> logging.Logger:
    """Настраивает логгер plan_generator с датой/временем и лимитом строк."""
    logger = logging.getLogger("plan_generator")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(isinstance(h, TruncatingFileHandler) for h in logger.handlers):
        # Уберём старые FileHandler без обрезки
        for h in list(logger.handlers):
            if isinstance(h, logging.FileHandler):
                logger.removeHandler(h)
                h.close()
        handler = TruncatingFileHandler(log_path, max_lines=MAX_LOG_LINES)
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s",
                datefmt=TIMESTAMP_FMT,
            )
        )
        logger.addHandler(handler)
    return logger


def append_update_log(message: str, base_dir: str) -> None:
    """Пишет в update.log строку с датой/временем и обрезает до лимита."""
    path = os.path.join(base_dir, UPDATE_LOG_FILENAME)
    line = f"[{now_timestamp()}] {message.rstrip()}\n"
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
        trim_log_file(path, MAX_LOG_LINES)
    except OSError:
        pass
