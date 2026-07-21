import re

import pandas as pd

_DISPLAY_OVERRIDES = {
    "xGDifference": "xG Difference",
    "xGConceded": "xG Conceded",
    "PossessionWonFinal3rdPerMatch": "Possession Won Final 3rd Per Match",
}


def display_name(name: str) -> str:
    """Human-readable, space-separated form of a canonical stat name, e.g.
    "GoalsPerGame" -> "Goals Per Game". Used for UI display only; canonical
    names (dict keys) elsewhere are unaffected."""
    if name in _DISPLAY_OVERRIDES:
        return _DISPLAY_OVERRIDES[name]
    words = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+", name)
    return " ".join(words) if words else name


def resolve_single(df: pd.DataFrame, candidates: list) -> str | None:
    """Find the first column in df matching any candidate name (case/whitespace-insensitive)."""
    columns_lower = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        key = str(cand).lower().strip()
        if key in columns_lower:
            return columns_lower[key]
    return None


def resolve_stats(df: pd.DataFrame, canonical_stats: list, stat_meta: dict) -> dict:
    """For each canonical stat name, find a matching column via its configured aliases.
    Returns canonical -> column name, or None if no alias matched."""
    columns_lower = {c.lower().strip(): c for c in df.columns}
    resolved = {}
    for stat in canonical_stats:
        candidates = [stat] + stat_meta.get(stat, {}).get("aliases", [])
        match = None
        for cand in candidates:
            key = str(cand).lower().strip()
            if key in columns_lower:
                match = columns_lower[key]
                break
        resolved[stat] = match
    return resolved
