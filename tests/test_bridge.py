"""Тесты JSON-RPC bridge handlers."""

import json

from bridge import handlers


def test_ping_and_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PLAN_BASE_DIR", str(tmp_path))
    (tmp_path / "version.txt").write_text("1.1.0", encoding="utf-8")
    assert handlers.dispatch("ping", {})["ok"] is True
    assert handlers.dispatch("ping", {})["version"] == "1.1.0"
    cfg = handlers.dispatch("config.get", {})
    assert cfg["export_admissions"] is False
    assert cfg["version"] == "1.1.0"
    assert cfg["ui_appearance"] == "Dark"
    handlers.dispatch("config.save", {"export_admissions": True, "ui_appearance": "Light"})
    cfg2 = handlers.dispatch("config.get", {})
    assert cfg2["export_admissions"] is True
    assert cfg2["ui_appearance"] == "Light"


def test_unknown_method_raises():
    try:
        handlers.dispatch("no.such", {})
        assert False, "expected error"
    except RuntimeError as e:
        assert "Unknown method" in str(e)


def test_diag_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PLAN_BASE_DIR", str(tmp_path))
    (tmp_path / "version.txt").write_text("1.1.0", encoding="utf-8")
    from patient_parser import patient_parser

    patient_parser.custom_diag_file = str(tmp_path / "custom_diagnoses.json")
    patient_parser.diagnosis_map["тест ключ"] = ("Диагноз", "Операция")
    out = tmp_path / "export.json"
    handlers.dispatch("diag.export", {"path": str(out)})
    data = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_setup_status_reports_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PLAN_BASE_DIR", str(tmp_path))
    (tmp_path / "version.txt").write_text("1.1.0", encoding="utf-8")
    status = handlers.dispatch("setup.status", {})
    assert status["base_dir"]
    assert "credentials_ok" in status
    assert "calendars_ready" in status
    assert isinstance(status["steps"], list)
    assert len(status["steps"]) >= 1
    # Windows cp125x cannot encode U+2192; keep bridge strings free of arrows.
    blob = json.dumps(status, ensure_ascii=False)
    assert "\u2192" not in blob


def test_bridge_write_emits_utf8_bytes_with_arrow():
    from bridge import cli

    class Buf:
        def __init__(self):
            self.data = b""

        def write(self, b):
            self.data += b

        def flush(self):
            pass

    class Out:
        def __init__(self, buf):
            self.buffer = buf

        def write(self, s):
            raise AssertionError("text write should not be used")

        def flush(self):
            pass

    buf = Buf()
    import bridge.cli as cli_mod

    old = cli_mod.sys.stdout
    cli_mod.sys.stdout = Out(buf)
    try:
        cli._write({"id": 1, "result": {"hint": "a \u2192 b"}})
    finally:
        cli_mod.sys.stdout = old
    assert "\u2192".encode("utf-8") in buf.data
    assert json.loads(buf.data.decode("utf-8"))["result"]["hint"] == "a \u2192 b"


def test_iter_request_lines_decodes_utf8_cyrillic_path():
    """Electron sends UTF-8; must not decode as cp1251 (mojibake paths)."""
    from bridge import cli

    path = r"C:\Users\SalikhovDmA\Desktop\Салихов Д.А\Календарь\План операций.xlsx"
    raw_line = (
        json.dumps(
            {"id": 7, "method": "plan.export", "params": {"output_path": path}},
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")

    class FakeBuf:
        def __iter__(self):
            yield raw_line

    class FakeStdin:
        buffer = FakeBuf()

    import bridge.cli as cli_mod

    old = cli_mod.sys.stdin
    cli_mod.sys.stdin = FakeStdin()
    try:
        lines = list(cli._iter_request_lines())
    finally:
        cli_mod.sys.stdin = old

    assert len(lines) == 1
    req = json.loads(lines[0])
    assert req["params"]["output_path"] == path
    # Classic mojibake must not appear
    assert "РџР»Р°РЅ" not in req["params"]["output_path"]


def test_as_day_map_dict_and_list():
    assert handlers._as_day_map({0: "А", "1": "Б"}) == {0: "А", 1: "Б"}
    assert handlers._as_day_map(["X", "Y"]) == {0: "X", 1: "Y"}
    assert handlers._as_day_map(None) == {}
