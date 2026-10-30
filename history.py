"""Operation history (JSON lines) and the per-printer tally of ink the counter
does not know about.

When a cleaning is run with "restore the counter", the ink still goes to the
pad but the printer's counter is rewound. The points rewound are added to a
tally per serial number so the real pad level can be estimated and warned about.
A permanent reset (new pads) clears the tally.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

DATA = Path(__file__).resolve().parent / "data"


def _history_path() -> Path:
    return DATA / "history.jsonl"


def _state_path() -> Path:
    return DATA / "state.json"


def record(kind: str, model: str, serial: str, **details) -> dict:
    """Append one event. Never raises: a full disk must not break a maintenance job."""
    entry = {"when": datetime.now().isoformat(timespec="seconds"), "kind": kind,
             "model": model, "serial": serial, **details}
    try:
        DATA.mkdir(exist_ok=True)
        with _history_path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return entry


def load(limit: int = 200, serial: str = "") -> List[dict]:
    """Newest first. Lines that are not valid JSON are skipped."""
    try:
        lines = _history_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events = []
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and (not serial or event.get("serial") == serial):
            events.append(event)
    return events[::-1][:limit]


def printers() -> List[dict]:
    """Every printer that appears in the history, newest first, so past work can be
    consulted with no printer connected: [{'serial', 'model', 'last'}]."""
    seen: Dict[str, dict] = {}
    for event in load(limit=10 ** 9):  # newest first: the first sighting is the latest
        serial = event.get("serial")
        if serial and serial not in seen:
            seen[serial] = {"serial": serial, "model": event.get("model", ""),
                            "last": event.get("when", "")}
    return list(seen.values())


def _load_state() -> Dict[str, dict]:
    try:
        state = json.loads(_state_path().read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(state: Dict[str, dict]) -> None:
    try:
        DATA.mkdir(exist_ok=True)
        _state_path().write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass


def hidden_points(serial: str) -> int:
    value = _load_state().get(serial, {}).get("hidden_points", 0)
    return value if isinstance(value, int) and value > 0 else 0


def add_hidden(serial: str, points: int) -> int:
    """Add rewound points to the tally; returns the new total."""
    state = _load_state()
    total = hidden_points(serial) + max(int(points), 0)
    state.setdefault(serial, {})["hidden_points"] = total
    _save_state(state)
    return total


def clear_hidden(serial: str) -> None:
    state = _load_state()
    if serial in state:
        state[serial]["hidden_points"] = 0
        _save_state(state)
