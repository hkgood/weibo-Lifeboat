from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class AppPrefs:
    last_config_path: str = "config.json"


def _prefs_path() -> Path:
    # Keep it dead-simple and dependency-free.
    return Path.home() / ".weibo_backup_gui.json"


def load_prefs() -> AppPrefs:
    p = _prefs_path()
    try:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            return AppPrefs(last_config_path=str(data.get("last_config_path") or "config.json"))
    except Exception:
        pass
    return AppPrefs()


def save_prefs(prefs: AppPrefs) -> None:
    p = _prefs_path()
    try:
        p.write_text(json.dumps({"last_config_path": prefs.last_config_path}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # best-effort
        return


def load_config(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(path: Path, cfg: Dict[str, Any]) -> None:
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def get_nested(cfg: Dict[str, Any], keys: list[str], default: Any = None) -> Any:
    cur: Any = cfg
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def set_nested(cfg: Dict[str, Any], keys: list[str], value: Any) -> None:
    cur: Any = cfg
    for k in keys[:-1]:
        nxt = cur.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[k] = nxt
        cur = nxt
    cur[keys[-1]] = value


def safe_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def safe_float(v: Any, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return default


def ensure_config_shape(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure minimal keys exist so the GUI can edit config safely.
    Doesn't try to validate semantics; just makes missing sections editable.
    """
    cfg.setdefault("weibo", {})
    cfg.setdefault("crawler", {})
    cfg.setdefault("storage", {})
    return cfg


def config_path_from_optional(s: Optional[str]) -> Optional[Path]:
    if not s:
        return None
    return Path(s).expanduser()


