"""Inspect source configuration without making network calls."""

from __future__ import annotations

from src.utils.config import load_yaml_config


def main() -> int:
    config = load_yaml_config("sources")
    sources = config.get("sources", {})
    enabled = [name for name, settings in sources.items() if settings.get("enabled")]
    disabled = [name for name, settings in sources.items() if not settings.get("enabled")]

    print("Enabled sources:", ", ".join(enabled) if enabled else "none")
    print("Disabled sources:", ", ".join(disabled) if disabled else "none")
    print("TODO: implement authenticated source health checks in a dedicated ingestion branch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
