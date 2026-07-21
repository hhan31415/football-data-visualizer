import pandas as pd


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
