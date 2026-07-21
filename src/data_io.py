import pandas as pd


def load_csv(uploaded_file) -> pd.DataFrame:
    """Read an uploaded CSV, falling back to latin-1 for files that aren't
    valid UTF-8 (common in NCAA.com exports with accented player names)."""
    try:
        return pd.read_csv(uploaded_file)
    except UnicodeDecodeError:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        return pd.read_csv(uploaded_file, encoding="latin-1")


def apply_missing_filter(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Drop rows missing or zero in `column`. Falls back to a blank/NaN-only
    check when the column isn't numeric."""
    series = df[column]
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any():
        mask = numeric.notna() & (numeric != 0)
    else:
        mask = series.notna() & (series.astype(str).str.strip() != "")
    return df[mask]
