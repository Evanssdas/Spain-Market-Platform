from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path = "config.yaml") -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a YAML mapping.")
    ensure_directories(config)
    return config


def ensure_directories(config: dict[str, Any]) -> None:
    paths = config.get("paths", {})
    for key in ("raw_dir", "processed_dir", "models_dir", "reports_dir", "logs_dir"):
        value = paths.get(key)
        if value:
            Path(value).mkdir(parents=True, exist_ok=True)
