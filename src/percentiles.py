import pandas as pd


def compute_percentiles(
    df: pd.DataFrame,
    resolved_cols: dict,
    stat_meta: dict,
    position_col: str = None,
    positions: list = None,
) -> pd.DataFrame:
    """Compute a 0-100 percentile rank per canonical stat.

    resolved_cols: canonical stat name -> actual column name (entries with
    no resolved column are skipped).
    stat_meta: canonical stat name -> {"lower_is_better": bool, ...}; when
    true, the percentile is flipped (100 - x) so a higher slice always means
    "better", regardless of whether the raw stat is normally minimized.
    position_col/positions: if given, restricts the baseline population used
    to compute percentiles to rows where position_col is in positions.

    NaN values are excluded from ranking (pandas' rank(pct=True) default)
    rather than being treated as 0.
    """
    base = df
    if position_col and positions:
        base = base[base[position_col].isin(positions)]

    out = pd.DataFrame(index=base.index)
    for stat, col in resolved_cols.items():
        if col is None:
            continue
        values = pd.to_numeric(base[col], errors="coerce")
        pct = values.rank(pct=True) * 100
        if stat_meta.get(stat, {}).get("lower_is_better", False):
            pct = 100 - pct
        out[stat] = pct
    return out
