import logging
import re
from unittest.mock import mock_open

import app_logging
from app_logging import (
    TruncatingFileHandler,
    append_update_log,
    now_timestamp,
    read_log_tail,
    setup_app_logger,
    trim_log_file,
    trim_text_lines,
)


def test_trim_text_lines_keeps_tail_and_newline():
    assert trim_text_lines("one\ntwo\nthree\n", 2) == "two\nthree\n"
    assert trim_text_lines("one\ntwo", 5) == "one\ntwo"


def test_trim_log_file_and_read_tail(tmp_path):
    path = tmp_path / "app.log"
    path.write_text("".join(f"{i}\n" for i in range(10)), encoding="utf-8")
    trim_log_file(str(path), 3)
    assert path.read_text(encoding="utf-8") == "7\n8\n9\n"
    assert read_log_tail(str(path), 2) == "8\n9\n"


def test_timestamp_has_expected_format():
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", now_timestamp())


def test_truncating_handler_leaves_at_most_500_lines(tmp_path):
    path = tmp_path / "handler.log"
    logger = logging.getLogger("test.truncating_handler")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = TruncatingFileHandler(str(path), max_lines=500)
    logger.addHandler(handler)
    for index in range(510):
        logger.info("line %s", index)
    handler.close()
    assert len(path.read_text(encoding="utf-8").splitlines()) <= 500


def test_setup_app_logger_configures_truncating_file_handler(tmp_path):
    logger = setup_app_logger(str(tmp_path / "configured.log"))
    assert any(isinstance(handler, TruncatingFileHandler) for handler in logger.handlers)


def test_append_update_log_writes_timestamped_line(tmp_path):
    append_update_log("updated", str(tmp_path))
    assert "updated" in (tmp_path / "update.log").read_text(encoding="utf-8")


def test_log_helpers_handle_missing_empty_and_os_errors(tmp_path, monkeypatch):
    missing = tmp_path / "missing.log"
    trim_log_file(str(missing))
    assert read_log_tail(str(missing)) == ""

    empty = tmp_path / "empty.log"
    empty.write_text("", encoding="utf-8")
    trim_log_file(str(empty))

    monkeypatch.setattr(app_logging.os.path, "exists", lambda _: True)
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("denied")))
    trim_log_file("denied.log")
    assert read_log_tail("denied.log") == ""
    append_update_log("denied", str(tmp_path))


def test_setup_replaces_old_file_handler_and_reuses_truncating_handler(tmp_path):
    logger = logging.getLogger("plan_generator")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    old_handler = logging.FileHandler(tmp_path / "old.log")
    logger.addHandler(old_handler)
    configured = setup_app_logger(str(tmp_path / "new.log"))
    assert old_handler not in configured.handlers
    assert setup_app_logger(str(tmp_path / "ignored.log")) is configured
