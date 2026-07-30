"""JSON-RPC bridge over stdin/stdout for Electron UI."""

from __future__ import annotations

import io
import json
import os
import sys
import traceback


def _force_utf8_stdio() -> None:
    """Windows charmap (cp1251/cp1252) cannot encode arrows etc. in JSON replies."""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
            continue
        except (AttributeError, OSError, ValueError):
            pass
        buf = getattr(stream, "buffer", None)
        if buf is None:
            continue
        try:
            wrapped = io.TextIOWrapper(
                buf,
                encoding="utf-8",
                errors="replace",
                line_buffering=True,
                write_through=True,
            )
            setattr(sys, name, wrapped)
        except (OSError, ValueError, AttributeError):
            pass


_force_utf8_stdio()


def _bootstrap() -> str:
    root = os.environ.get("PLAN_BASE_DIR")
    if not root:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(root)
    if root not in sys.path:
        sys.path.insert(0, root)
    os.environ["PLAN_BASE_DIR"] = root
    return root


ROOT = _bootstrap()

from bridge import handlers  # noqa: E402


def _write(obj: dict) -> None:
    """Always emit UTF-8 bytes so Windows cp125x stdout cannot break JSON."""
    line = json.dumps(obj, ensure_ascii=False, default=str) + "\n"
    buf = getattr(sys.stdout, "buffer", None)
    if buf is not None:
        buf.write(line.encode("utf-8", errors="replace"))
        buf.flush()
        return
    sys.stdout.write(line)
    sys.stdout.flush()


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req_id = None
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params") or {}
            if not isinstance(params, dict):
                params = {}
            result = handlers.dispatch(method, params)
            _write({"id": req_id, "result": result})
        except Exception as e:
            tb = traceback.format_exc()
            try:
                sys.stderr.write(tb)
                sys.stderr.flush()
            except UnicodeEncodeError:
                sys.stderr.buffer.write(tb.encode("utf-8", errors="replace"))
            _write(
                {
                    "id": req_id,
                    "error": {
                        "message": str(e),
                    },
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
