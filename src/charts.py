import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PRIMARY_COLOR = "#2563eb"  # blue
COMPARE_COLOR = "#dc2626"  # red

# Overrides for the base scatter point cloud's color-by-position; any position
# value not listed here still gets an auto-assigned color from Plotly's
# default qualitative palette. Covers both the "general" dataset's
# position_group values and NCAA's short position codes.
POSITION_COLOR_OVERRIDES = {
    "defenders": "#16a34a",
    "Defenders": "#16a34a",
    "defender": "#16a34a",
    "Defender": "#16a34a",
    "D": "#16a34a",
    "midfielders": PRIMARY_COLOR,
    "Midfielders": PRIMARY_COLOR,
    "midfielder": PRIMARY_COLOR,
    "Midfielder": PRIMARY_COLOR,
    "M": PRIMARY_COLOR,
    "attackers": COMPARE_COLOR,
    "Attackers": COMPARE_COLOR,
    "attacker": COMPARE_COLOR,
    "Attacker": COMPARE_COLOR,
    "F": COMPARE_COLOR,
}


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
        polar=dict(radialaxis=dict(tickfont=dict(color="#696E77"))),
    )
    return fig


def build_scatter(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    x_label: str,
    y_label: str,
    entity_col: str,
    highlight: list = None,
    color_col: str = None,
    show_trend: bool = False,
    show_avg_lines: bool = False,
    label_col: str = None,
):
    """Scatter every row in `df` by (x_col, y_col). Optionally colors the base
    cloud by `color_col` (e.g. position), overlays a manual least-squares trend
    line and/or mean reference lines, and draws each (name, color) in
    `highlight` as its own distinct, larger point on top of the cloud.

    `entity_col` is the raw identity column used to match `highlight` names;
    `label_col` (defaults to `entity_col`) is what's actually shown in hover
    text and highlight legend entries, e.g. a "Name (Team)" display column."""
    hover_col = label_col or entity_col
    cols = list({entity_col, x_col, y_col, hover_col} | ({color_col} if color_col else set()))
    plot_df = df[cols].copy()
    plot_df[x_col] = pd.to_numeric(plot_df[x_col], errors="coerce")
    plot_df[y_col] = pd.to_numeric(plot_df[y_col], errors="coerce")
    plot_df = plot_df.dropna(subset=[x_col, y_col])

    fig = px.scatter(
        plot_df,
        x=x_col,
        y=y_col,
        color=color_col if color_col else None,
        color_discrete_map=POSITION_COLOR_OVERRIDES if color_col else None,
        hover_name=hover_col,
        labels={x_col: x_label, y_col: y_label},
    )
    fig.update_traces(marker=dict(size=7, opacity=0.6))

    if show_trend and len(plot_df) >= 2:
        xs = plot_df[x_col].to_numpy()
        ys = plot_df[y_col].to_numpy()
        slope, intercept = np.polyfit(xs, ys, 1)
        x_range = [float(xs.min()), float(xs.max())]
        y_fit = [slope * x + intercept for x in x_range]
        fig.add_trace(
            go.Scatter(
                x=x_range,
                y=y_fit,
                mode="lines",
                name="Trend",
                line=dict(color="#f59e0b", dash="dash"),
                hoverinfo="skip",
            )
        )

    if show_avg_lines and len(plot_df) > 0:
        fig.add_hline(y=plot_df[y_col].mean(), line_dash="dot", line_color="gray")
        fig.add_vline(x=plot_df[x_col].mean(), line_dash="dot", line_color="gray")

    for name, color in highlight or []:
        match = plot_df[plot_df[entity_col] == name]
        if match.empty:
            continue
        display_name = match[hover_col].iloc[0]
        fig.add_trace(
            go.Scatter(
                x=match[x_col],
                y=match[y_col],
                mode="markers",
                name=display_name,
                marker=dict(size=14, color=color, line=dict(width=1, color="white")),
                hovertemplate=(
                    f"<b>{display_name}</b><br>{x_label}: %{{x}}<br>{y_label}: %{{y}}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        legend_title_text="",
        margin=dict(t=20, b=20, l=20, r=20),
        font=dict(size=11),
        xaxis_title=x_label,
        yaxis_title=y_label,
        height=650,
    )
    return fig
