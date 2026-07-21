import pandas as pd
import streamlit as st

from src import charts, config_loader, data_io, percentiles, stat_resolver

st.set_page_config(page_title="Soccer Stat Wheel", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem; padding-bottom: 1rem;}
    h1 {font-size: 1.3rem !important; margin-bottom: 0.3rem;}
    h2, h3 {font-size: 0.95rem !important; margin-top: 0.2rem; margin-bottom: 0.2rem;}
    label, .stRadio label p, .stSelectbox label p, .stMultiSelect label p,
    div[data-testid="stMarkdownContainer"] p, .stCaption {
        font-size: 0.78rem !important;
    }
    div[data-testid="stFileUploaderDropzone"] {padding: 0.4rem;}
    div[data-baseweb="select"] {font-size: 0.78rem;}
    .stDataFrame {font-size: 0.75rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Football Data Visualizer")


def stat_table(active_stats, raw, values):
    return pd.DataFrame(
        {
            "Stat": active_stats,
            "Value": raw,
            "Percentile": [round(v, 1) if v is not None else None for v in values],
        }
    )


row0 = st.columns(2)
with row0[0]:
    mode_label = st.radio("Mode", ["Team Stats", "Individual Stats"], horizontal=True)
    mode = "team" if mode_label == "Team Stats" else "individual"
with row0[1]:
    dataset_label = st.radio(
        "Dataset", ["General", "NCAA"], horizontal=True,
        help="General is dataset-agnostic for any "
        "team/player CSV. NCAA uses the built-in NCAA soccer stat presets.",
    )
    dataset = "ncaa" if dataset_label == "NCAA" else "general"

aliases_cfg = config_loader.load_aliases(dataset, mode)
stat_meta = aliases_cfg["stats"]
presets = config_loader.load_presets(dataset, mode)

uploaded = st.file_uploader(f"Upload {mode_label} CSV", type="csv", key="primary_csv")

if uploaded is None:
    st.info("Upload a CSV to get started.")
    st.stop()

df = data_io.load_csv(uploaded)

entity_col = stat_resolver.resolve_single(df, aliases_cfg.get("entity_column", []))
if entity_col is None:
    st.error("Could not find a name/team identity column in this CSV.")
    st.stop()

position_col = stat_resolver.resolve_single(df, aliases_cfg.get("position_column", []))

row1 = st.columns(3) if position_col else st.columns(2)
with row1[0]:
    filter_col = st.selectbox(
        "Exclude rows missing/zero in", ["(none)"] + list(df.columns)
    )
    if filter_col != "(none)":
        df = data_io.apply_missing_filter(df, filter_col)

position_filter = None
if position_col:
    with row1[1]:
        positions_available = sorted(df[position_col].dropna().unique().tolist())
        position_filter = st.multiselect("Restrict baseline to positions", positions_available)
        if not position_filter:
            position_filter = None
    preset_col = row1[2]
else:
    preset_col = row1[1]

with preset_col:
    preset_names = list(presets.keys()) + ["Custom"]
    preset_choice = st.selectbox("Preset", preset_names)

if preset_choice == "Custom":
    display_to_canonical = {}
    for canonical in stat_meta.keys():
        label = stat_resolver.display_name(canonical)
        if label in display_to_canonical:
            label = f"{label} ({canonical})"
        display_to_canonical[label] = canonical
    chosen_labels = st.multiselect(
        "Pick exactly 6 stats", sorted(display_to_canonical.keys()), max_selections=6
    )
    canonical_stats = [display_to_canonical[label] for label in chosen_labels]
    if len(canonical_stats) != 6:
        st.warning("Pick exactly 6 stats to continue.")
        st.stop()
else:
    canonical_stats = presets[preset_choice]

resolved = stat_resolver.resolve_stats(df, canonical_stats, stat_meta)

unresolved = [s for s, col in resolved.items() if col is None]
if unresolved:
    st.warning("Some preset stats weren't found automatically — pick their columns below:")
    resolve_cols = st.columns(len(unresolved))
    for c, stat in zip(resolve_cols, unresolved):
        with c:
            choice = st.selectbox(
                f"'{stat_resolver.display_name(stat)}'",
                ["(skip)"] + list(df.columns),
                key=f"resolve_{dataset}_{mode}_{stat}",
            )
            resolved[stat] = None if choice == "(skip)" else choice

active_stats = [s for s in canonical_stats if resolved.get(s)]
if not active_stats:
    st.error("No stats resolved — cannot build a chart.")
    st.stop()

active_stat_labels = [stat_resolver.display_name(s) for s in active_stats]

pct_df = percentiles.compute_percentiles(
    df,
    {s: resolved[s] for s in active_stats},
    stat_meta,
    position_col=position_col,
    positions=position_filter,
)

entities = df.loc[pct_df.index, entity_col].dropna().unique().tolist()
if not entities:
    st.error("No entities left after filtering — loosen the filter or position restriction.")
    st.stop()


def get_values(idx):
    return [pct_df.loc[idx, s] if idx in pct_df.index else None for s in active_stats]


def get_raw(idx):
    return [df.loc[idx, resolved[s]] for s in active_stats]


entity_word = "Team" if mode == "team" else "Player"

row2 = st.columns(3)
with row2[0]:
    comparison_mode = st.radio("Comparison", ["Vs League Average", "Head-to-Head"], horizontal=True)
with row2[1]:
    entity_label = f"{entity_word} 1" if comparison_mode == "Head-to-Head" else entity_word
    entity_name = st.selectbox(entity_label, entities)

entity_idx = df[df[entity_col] == entity_name].index[0]
entity_values = get_values(entity_idx)
entity_raw = get_raw(entity_idx)

compare_values = compare_raw = compare_name = None
if comparison_mode == "Vs League Average":
    baseline = df.loc[pct_df.index]
    compare_values = [50] * len(active_stats)
    compare_raw = [
        round(pd.to_numeric(baseline[resolved[s]], errors="coerce").mean(), 2)
        for s in active_stats
    ]
    compare_name = "League Average"
else:
    other_entities = [e for e in entities if e != entity_name]
    if not other_entities:
        st.warning("No other entity available to compare against.")
    else:
        with row2[2]:
            compare_entity = st.selectbox(f"{entity_word} 2", other_entities)
        compare_idx = df[df[entity_col] == compare_entity].index[0]
        compare_values = get_values(compare_idx)
        compare_raw = get_raw(compare_idx)
        compare_name = compare_entity

fig = charts.build_wheel(
    active_stat_labels,
    entity_values,
    entity_name,
    raw_values=entity_raw,
    compare_values=compare_values,
    compare_name=compare_name,
    compare_raw=compare_raw,
)
st.plotly_chart(fig, use_container_width=True)

table_cols = st.columns(2) if compare_values is not None else st.columns(1)
with table_cols[0]:
    st.caption(entity_name)
    st.dataframe(
        stat_table(active_stat_labels, entity_raw, entity_values),
        hide_index=True,
        use_container_width=True,
    )
if compare_values is not None:
    with table_cols[1]:
        st.caption(compare_name)
        st.dataframe(
            stat_table(active_stat_labels, compare_raw, compare_values),
            hide_index=True,
            use_container_width=True,
        )

st.divider()
st.subheader("Scatter Explorer")

scatter_presets = config_loader.load_scatter_presets(dataset, mode)

scatter_row = st.columns(3) if position_col else st.columns(2)
with scatter_row[0]:
    scatter_preset_names = list(scatter_presets.keys()) + ["Custom"]
    scatter_preset_choice = st.selectbox("Scatter preset", scatter_preset_names, key="scatter_preset")

scatter_position_filter = None
if position_col:
    with scatter_row[1]:
        scatter_positions_available = sorted(df[position_col].dropna().unique().tolist())
        scatter_position_filter = st.multiselect(
            "Restrict scatter to positions", scatter_positions_available, key="scatter_position_filter"
        )
        if not scatter_position_filter:
            scatter_position_filter = None
    scatter_checkbox_col = scatter_row[2]
else:
    scatter_checkbox_col = scatter_row[1]

if scatter_preset_choice == "Custom":
    scatter_display_to_canonical = {}
    for canonical in stat_meta.keys():
        label = stat_resolver.display_name(canonical)
        if label in scatter_display_to_canonical:
            label = f"{label} ({canonical})"
        scatter_display_to_canonical[label] = canonical
    scatter_sorted_labels = sorted(scatter_display_to_canonical.keys())
    custom_scatter_cols = st.columns(2)
    with custom_scatter_cols[0]:
        scatter_x_display = st.selectbox("X stat", scatter_sorted_labels, key="scatter_x")
    with custom_scatter_cols[1]:
        default_y_index = min(1, len(scatter_sorted_labels) - 1)
        scatter_y_display = st.selectbox(
            "Y stat", scatter_sorted_labels, index=default_y_index, key="scatter_y"
        )
    scatter_x_canonical = scatter_display_to_canonical[scatter_x_display]
    scatter_y_canonical = scatter_display_to_canonical[scatter_y_display]
else:
    scatter_pair = scatter_presets[scatter_preset_choice]
    scatter_x_canonical = scatter_pair["x"]
    scatter_y_canonical = scatter_pair["y"]

with scatter_checkbox_col:
    show_trend = st.checkbox("Show trend line", key="scatter_trend")
    show_avg_lines = st.checkbox("Show average lines", key="scatter_avg_lines")

scatter_resolved = stat_resolver.resolve_stats(df, [scatter_x_canonical, scatter_y_canonical], stat_meta)
scatter_unresolved = [s for s, col in scatter_resolved.items() if col is None]
if scatter_unresolved:
    st.warning("Some scatter stats weren't found automatically — pick their columns below:")
    scatter_resolve_cols = st.columns(len(scatter_unresolved))
    for c, stat in zip(scatter_resolve_cols, scatter_unresolved):
        with c:
            choice = st.selectbox(
                f"'{stat_resolver.display_name(stat)}'",
                ["(skip)"] + list(df.columns),
                key=f"scatter_resolve_{dataset}_{mode}_{stat}",
            )
            scatter_resolved[stat] = None if choice == "(skip)" else choice

if scatter_resolved[scatter_x_canonical] and scatter_resolved[scatter_y_canonical]:
    scatter_df = df
    if scatter_position_filter and position_col:
        scatter_df = scatter_df[scatter_df[position_col].isin(scatter_position_filter)]

    scatter_highlight = [(entity_name, charts.PRIMARY_COLOR)]
    if comparison_mode == "Head-to-Head" and compare_values is not None:
        scatter_highlight.append((compare_name, charts.COMPARE_COLOR))

    scatter_fig = charts.build_scatter(
        scatter_df,
        scatter_resolved[scatter_x_canonical],
        scatter_resolved[scatter_y_canonical],
        stat_resolver.display_name(scatter_x_canonical),
        stat_resolver.display_name(scatter_y_canonical),
        entity_col,
        highlight=scatter_highlight,
        color_col=position_col,
        show_trend=show_trend,
        show_avg_lines=show_avg_lines,
    )
    scatter_display_cols = st.columns([1, 3, 1])
    with scatter_display_cols[1]:
        st.plotly_chart(scatter_fig, use_container_width=True)
else:
    st.info("Pick valid columns for both scatter stats to render the plot.")
