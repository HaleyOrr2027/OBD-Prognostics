"""Step 01: configuration loading.

Minimal version written to unblock the mode detector (Steps 12-25). Every
threshold the detector uses comes from config/*.yaml through this module;
no other module reads YAML directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
CONFIG_FILES = ("pids", "modes", "windows", "models", "runtime")


class ConfigError(ValueError):
    """Raised with an actionable message when configuration is missing or invalid."""


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Missing config file: {path}")
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")
    if "version" not in data:
        raise ConfigError(f"{path} is missing the required 'version' key")
    return data


@dataclass
class Config:
    pids: dict[str, Any]
    modes: dict[str, Any]
    windows: dict[str, Any] = field(default_factory=dict)
    models: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)
    root: Path = REPO_ROOT

    def get(self, section: str, *keys: str) -> Any:
        """Read a nested value, failing loudly if any key is absent."""
        node: Any = getattr(self, section)
        trail = section
        for key in keys:
            trail += f".{key}"
            if not isinstance(node, dict) or key not in node:
                raise ConfigError(f"Missing config key: {trail}")
            node = node[key]
        return node

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    def version_tag(self) -> str:
        return f"pids-v{self.pids['version']}_modes-v{self.modes['version']}"


def load_config(config_dir: str | Path | None = None) -> Config:
    directory = Path(config_dir) if config_dir else CONFIG_DIR
    loaded = {name: _load_yaml(directory / f"{name}.yaml") for name in CONFIG_FILES}
    for required in ("required", "pids"):
        if required not in loaded["pids"]:
            raise ConfigError(f"config/pids.yaml is missing '{required}'")
    return Config(**loaded, root=directory.parent)
