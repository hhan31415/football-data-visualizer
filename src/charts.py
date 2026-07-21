import pandas as pd
import plotly.express as px


def build_wheel(
    labels: list,
    entity_values: list,
    entity_name: str,
    raw_values: list = None,
    compare_values: list = None,
    compare_name: str = None,
    compare_raw: list = None,
    kind: str = "bar_polar",
):
    """Build a percentile wheel figure: one wedge/vertex per stat in `labels`,
    plotting `entity_values` (0-100 percentiles) and optionally a second
    series (`compare_values`, e.g. league average or a head-to-head entity).
    `kind` is "bar_polar" (wedges) or "line_polar" (radar polygon)."""
    rows = []
    for i, label in enumerate(labels):
        rows.append(
            {
                "stat": label,
                "percentile": entity_values[i],
                "raw": raw_values[i] if raw_values else None,
                "entity": entity_name,
            }
        )
    if compare_values is not None:
        for i, label in enumerate(labels):
            rows.append(
                {
                    "stat": label,
                    "percentile": compare_values[i],
                    "raw": compare_raw[i] if compare_raw else None,
                    "entity": compare_name,
                }
            )
    data = pd.DataFrame(rows)

    if kind == "bar_polar":
        fig = px.bar_polar(
            data,
            r="percentile",
            theta="stat",
            color="entity",
            barmode="overlay",
            hover_data={"raw": True, "percentile": ":.0f"},
            range_r=[0, 100],
        )
        fig.update_traces(opacity=0.7)
    else:
        fig = px.line_polar(
            data,
            r="percentile",
            theta="stat",
            color="entity",
            line_close=True,
            hover_data={"raw": True, "percentile": ":.0f"},
            range_r=[0, 100],
        )
        fig.update_traces(fill="toself", opacity=0.6)

    fig.update_layout(legend_title_text="")
    return fig
