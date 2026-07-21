from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

DATASETS = ["ncaa", "general"]


def _load_yaml(filename: str) -> dict:
    path = CONFIG_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_aliases(dataset: str, mode: str) -> dict:
    """Return the alias config for a (dataset, mode) pair, e.g. ("ncaa", "team")
    or ("general", "individual"): entity_column, position_column, and the
    stats mapping (canonical name -> {lower_is_better, aliases})."""
    return _load_yaml(f"{dataset}_{mode}_aliases.yaml")


def load_presets(dataset: str, mode: str) -> dict:
    """Return preset name -> list of canonical stat names for a (dataset, mode) pair."""
    return _load_yaml(f"{dataset}_{mode}_presets.yaml")["presets"]
