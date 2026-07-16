from datetime import date
import json

from gui import helpers


def test_save_and_load_config_with_temp_paths(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    old_path = tmp_path / "old.json"
    monkeypatch.setattr(helpers, "CONFIG_FILE", str(config_path))
    monkeypatch.setattr(helpers, "OLD_CONFIG_FILE", str(old_path))
    helpers.save_config("/tmp/output", date(2026, 6, 29))
    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "last_dir": "/tmp/output",
        "last_monday": "2026-06-29",
    }
    assert helpers.load_config() == {
        "last_dir": "/tmp/output",
        "last_monday": date(2026, 6, 29),
    }


def test_load_config_migrates_old_path_and_handles_invalid_date(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    old_path = tmp_path / "old.json"
    old_path.write_text('{"last_dir": "/legacy"}', encoding="utf-8")
    config_path.write_text('{"last_monday": "not-a-date"}', encoding="utf-8")
    monkeypatch.setattr(helpers, "CONFIG_FILE", str(config_path))
    monkeypatch.setattr(helpers, "OLD_CONFIG_FILE", str(old_path))
    assert helpers.load_config() == {"last_dir": "/legacy", "last_monday": None}
    assert not old_path.exists()


def test_tag_for_log_line_success_and_error():
    assert helpers.tag_for_log_line("2026-07-16 - ERROR - Ошибка загрузки") == "error"
    assert helpers.tag_for_log_line("2026-07-16 - WARNING - нет событий") == "warning"
    assert helpers.tag_for_log_line("[12:00] События успешно загружены") == "success"
    assert helpers.tag_for_log_line("Не удалось создать план") == "error"
    assert helpers.tag_for_log_line("Обработка событий...") == "info"
