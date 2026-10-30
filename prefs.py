"""Small per-user preferences (window geometry, last page, EEPROM range) in
data/prefs.json.

Nothing here changes what is sent to a printer: the cleaning mode and the "restore
the counter" box are deliberately NOT remembered, so a dangerous choice is never
preselected by a previous session.
"""
import json
from typing import Any, Dict

import history


def _path():
    return history.DATA / "prefs.json"


def load() -> Dict[str, Any]:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(**values: Any) -> None:
    """Merge values into the file. Never raises: preferences are not worth an error."""
    data = load()
    data.update(values)
    try:
        history.DATA.mkdir(exist_ok=True)
        _path().write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def get_int(name: str, default: int, low: int, high: int) -> int:
    """An integer preference clamped to [low, high]; the default if missing or damaged."""
    value = load().get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(low, min(high, value))
