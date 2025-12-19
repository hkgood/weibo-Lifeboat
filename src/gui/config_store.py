from __future__ import annotations

import json
import sys
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class AppPrefs:
    last_config_path: str = "config.json"


def _prefs_path() -> Path:
    # Keep it dead-simple and dependency-free.
    return Path.home() / ".weibo_backup_gui.json"


def _get_user_config_dir() -> Path:
    """获取用户配置目录（可写）"""
    if sys.platform == "darwin":
        config_dir = Path.home() / "Library" / "Application Support" / "WeiboLifeboat"
    elif sys.platform == "win32":
        config_dir = Path.home() / "AppData" / "Local" / "WeiboLifeboat"
    else:
        config_dir = Path.home() / ".weibo-lifeboat"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def _get_user_data_dir() -> Path:
    """获取用户数据目录（存放数据库、图片、视频等）"""
    if sys.platform == "darwin":
        # macOS: ~/Documents/WeiboLifeboat/
        data_dir = Path.home() / "Documents" / "WeiboLifeboat"
    elif sys.platform == "win32":
        # Windows: %USERPROFILE%\Documents\WeiboLifeboat\
        data_dir = Path.home() / "Documents" / "WeiboLifeboat"
    else:
        # Linux: ~/Documents/WeiboLifeboat/
        data_dir = Path.home() / "Documents" / "WeiboLifeboat"
    
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _get_default_config_path() -> Path:
    """获取默认配置文件路径（用户可写目录）"""
    return _get_user_config_dir() / "config.json"


def _ensure_user_config_exists() -> Path:
    """确保用户配置文件存在，如果不存在则从模板复制"""
    user_config = _get_default_config_path()
    data_dir = _get_user_data_dir()
    
    if not user_config.exists():
        # 创建新配置文件
        # 尝试从打包的模板复制
        if getattr(sys, 'frozen', False):
            # 打包后的路径
            template_path = Path(sys._MEIPASS) / "config.example.json"
        else:
            # 开发环境路径
            template_path = Path(__file__).resolve().parents[2] / "config.example.json"
        
        if template_path.exists():
            shutil.copy(template_path, user_config)
            # 读取配置并更新存储路径为用户文档目录
            try:
                config = json.loads(user_config.read_text(encoding="utf-8"))
                # 更新存储路径为绝对路径
                if "storage" not in config:
                    config["storage"] = {}
                config["storage"]["database_path"] = str(data_dir / "weibo.db")
                config["storage"]["images_dir"] = str(data_dir / "images")
                config["storage"]["videos_dir"] = str(data_dir / "videos")
                config["storage"]["output_dir"] = str(data_dir / "output")
                # 写回配置文件
                user_config.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass  # 如果更新失败，使用默认配置
        else:
            # 如果模板不存在，创建一个默认配置（使用文档目录）
            default_config = {
                "weibo": {
                    "user_id": "",
                    "cookie": "",
                    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                },
                "crawler": {
                    "request_delay": 1.0,
                    "timeout": 30
                },
                "storage": {
                    "database_path": str(data_dir / "weibo.db"),
                    "images_dir": str(data_dir / "images"),
                    "videos_dir": str(data_dir / "videos"),
                    "output_dir": str(data_dir / "output")
                }
            }
            user_config.write_text(json.dumps(default_config, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        # 配置文件已存在，检查并更新存储路径（如果是相对路径）
        try:
            config = json.loads(user_config.read_text(encoding="utf-8"))
            if "storage" in config:
                needs_update = False
                storage = config["storage"]
                
                # 检查路径是否需要更新（相对路径或旧的data/目录）
                for key in ["database_path", "images_dir", "videos_dir", "output_dir"]:
                    if key in storage:
                        path = storage[key]
                        # 如果是相对路径（如data/xxx），更新为文档目录
                        if not Path(path).is_absolute() or path.startswith("data/"):
                            needs_update = True
                            break
                
                if needs_update:
                    storage["database_path"] = str(data_dir / "weibo.db")
                    storage["images_dir"] = str(data_dir / "images")
                    storage["videos_dir"] = str(data_dir / "videos")
                    storage["output_dir"] = str(data_dir / "output")
                    user_config.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass  # 如果更新失败，继续使用现有配置
    
    return user_config


def load_prefs() -> AppPrefs:
    p = _prefs_path()
    try:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            last_path = str(data.get("last_config_path") or "")
            # 如果是默认值或者旧的相对路径，使用新的用户配置目录
            if not last_path or last_path == "config.json":
                last_path = str(_get_default_config_path())
            return AppPrefs(last_config_path=last_path)
    except Exception:
        pass
    
    # 默认使用用户配置目录
    return AppPrefs(last_config_path=str(_get_default_config_path()))


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
    # 确保目录存在
    path.parent.mkdir(parents=True, exist_ok=True)
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


