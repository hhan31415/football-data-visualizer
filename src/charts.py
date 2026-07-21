import pandas as pd
import plotly.express as px

PRIMARY_COLOR = "#2563eb"  # blue
COMPARE_COLOR = "#dc2626"  # red


def build_wheel(
    labels: list,
    entity_values: list,
    entity_name: str,
    raw_values: list = None,
    compare_values: list = None,
    compare_name: str = None,
    compare_raw: list = None,
):
    """Build a percentile radar chart: one vertex per stat in `labels`,
    plotting `entity_values` (0-100 percentiles) and optionally a second
    series (`compare_values`, e.g. league average or a head-to-head entity).
    Hover shows the exact percentile and raw stat value per point."""
    rows = [
        {
            "stat": label,
            "percentile": entity_values[i],
            "raw": raw_values[i] if raw_values else None,
            "entity": entity_name,
        }
        for i, label in enumerate(labels)
    ]
    color_map = {entity_name: PRIMARY_COLOR}
    if compare_values is not None:
        rows += [
            {
                "stat": label,
                "percentile": compare_values[i],
                "raw": compare_raw[i] if compare_raw else None,
                "entity": compare_name,
            }
            for i, label in enumerate(labels)
        ]
        color_map[compare_name] = COMPARE_COLOR

    data = pd.DataFrame(rows)

    fig = px.line_polar(
        data,
        r="percentile",
        theta="stat",
        color="entity",
        line_close=True,
        range_r=[0, 100],
        color_discrete_map=color_map,
    )
    fig.update_traces(fill="toself", opacity=0.5, mode="lines+markers", marker=dict(size=7))

    for trace in fig.data:
        sub = data[data["entity"] == trace.name]
        raw_col = sub["raw"].tolist()
        # line_close=True duplicates the first point at the end to close the
        # polygon, so customdata needs a matching duplicate or it misaligns
        # with every point on the trace, not just the last one.
        raw_col = raw_col + raw_col[:1]
        trace.customdata = [[v] for v in raw_col]
        trace.hovertemplate = (
            "<b>%{theta}</b><br>"
            + trace.name
            + "<br>Percentile: %{r:.0f}<br>Value: %{customdata[0]}<extra></extra>"
        )

    fig.update_layout(
        legend_title_text="",
        margin=dict(t=20, b=20, l=20, r=20),
        font=dict(size=11),
    )
    return fig
