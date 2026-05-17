"""Configuration loading helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def config_path(name: str) -> Path:
    candidate = Path(name)
    if candidate.suffix:
        return candidate
    return project_root() / "configs" / f"{name}.yaml"


def load_yaml_config(name: str) -> dict[str, Any]:
    path = config_path(name)
    with path.open("r", encoding="utf-8") as file:
        content = yaml.safe_load(file) or {}
    if not isinstance(content, dict):
        raise ValueError(f"Config at {path} must be a mapping.")
    return content


def load_all_configs() -> dict[str, dict[str, Any]]:
    return {
        "app": load_yaml_config("app"),
        "data_stage": load_yaml_config("data_stage"),
        "database": load_yaml_config("database"),
        "entity_resolution": load_yaml_config("entity_resolution"),
        "logging": load_yaml_config("logging"),
        "model": load_yaml_config("model"),
        "sources": load_yaml_config("sources"),
    }


def source_env_groups(settings: dict[str, Any]) -> list[list[str]]:
    primary_envs = [
        env_name
        for key, env_name in settings.items()
        if key.endswith("_env") and not key.startswith("fallback_") and isinstance(env_name, str)
    ]
    fallback_envs = [
        env_name
        for key, env_name in settings.items()
        if key.startswith("fallback_") and key.endswith("_env") and isinstance(env_name, str)
    ]

    groups: list[list[str]] = []
    if primary_envs:
        groups.append(primary_envs)
    if fallback_envs:
        groups.append(fallback_envs)
    return groups


def source_is_configured(settings: dict[str, Any]) -> bool:
    env_groups = source_env_groups(settings)
    if not env_groups:
        return True
    return any(all(os.getenv(env_name) for env_name in group) for group in env_groups)


def enabled_sources() -> dict[str, list[str]]:
    sources = load_yaml_config("sources").get("sources", {})
    enabled = [name for name, settings in sources.items() if settings.get("enabled")]
    disabled = [name for name, settings in sources.items() if not settings.get("enabled")]
    return {"enabled": enabled, "disabled": disabled}


def source_configuration_status() -> dict[str, list[str]]:
    sources = load_yaml_config("sources").get("sources", {})
    configured: list[str] = []
    missing: list[str] = []

    for source_name, settings in sources.items():
        if source_is_configured(settings):
            configured.append(source_name)
        else:
            missing.append(source_name)

    return {"configured": configured, "missing": missing}
