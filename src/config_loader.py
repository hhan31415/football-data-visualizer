from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _load_yaml(filename: str) -> dict:
    path = CONFIG_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_aliases(mode: str) -> dict:
    """Return the alias config for "team" or "individual": entity_column,
    position_column, and the stats mapping (canonical name -> {lower_is_better, aliases})."""
    return _load_yaml(f"{mode}_aliases.yaml")


def load_presets(mode: str) -> dict:
    """Return preset name -> list of canonical stat names for "team" or "individual"."""
    return _load_yaml(f"{mode}_presets.yaml")["presets"]
