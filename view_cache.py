"""Persist expensive read-only page views and refresh them off the request path."""

import json
import threading
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / "data" / "atlas-view-cache.json"
_lock = threading.Lock()
_running = set()


def _read():
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return {}


def _write(key, value):
    with _lock:
        saved = _read()
        saved[key] = {"day": date.today().isoformat(), "at": datetime.now(timezone.utc).isoformat(), "value": value}
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = CACHE_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(saved, separators=(",", ":")), encoding="utf-8")
        temporary.replace(CACHE_PATH)


def get(key, compute):
    """Return a saved view immediately; recompute it in the background."""
    saved = _read().get(key)
    if saved and saved.get("day") == date.today().isoformat():
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(saved["at"])).total_seconds()
        if age < 300:
            return saved["value"]
        with _lock:
            if key not in _running:
                _running.add(key)

                def refresh():
                    try:
                        _write(key, compute())
                    finally:
                        with _lock:
                            _running.discard(key)

                threading.Thread(target=refresh, daemon=True, name=f"view-cache-{key}").start()
        return saved["value"]
    value = compute()
    _write(key, value)
    return value
