"""JSON-RPC bridge over stdin/stdout for Electron UI."""

from __future__ import annotations

import json
import os
import sys
import traceback


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
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
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
            sys.stderr.write(tb)
            sys.stderr.flush()
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
