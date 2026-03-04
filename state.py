"""Persist state between runs (last fetch timestamp + processed IDs)."""
import json
from pathlib import Path

_STATE_FILE = Path("state.json")


def _load() -> dict:
    if _STATE_FILE.exists():
        return json.loads(_STATE_FILE.read_text())
    return {"last_run_epoch": None, "processed_ids": []}


def _save(state: dict) -> None:
    _STATE_FILE.write_text(json.dumps(state, indent=2))


def get_last_run_epoch() -> int | None:
    return _load().get("last_run_epoch")


def save_run(epoch: int, new_ids: list[str]) -> None:
    state = _load()
    state["last_run_epoch"] = epoch
    known = set(state.get("processed_ids", []))
    known.update(new_ids)
    # Keep only the last 2 000 IDs to prevent unbounded growth
    state["processed_ids"] = list(known)[-2000:]
    _save(state)


def get_processed_ids() -> set[str]:
    return set(_load().get("processed_ids", []))
