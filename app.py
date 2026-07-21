import pandas as pd
import streamlit as st

from src import charts, config_loader, data_io, percentiles, stat_resolver

st.set_page_config(page_title="Football Data Visualizer", layout="wide")

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

    /* Tab-styled look for the Mode selector, scoped by its aria-label so no
    other radio group on the page is affected. */
    div[role="radiogroup"][aria-label="Mode"] {
        gap: 0;
        border-bottom: 2px solid #e5e7eb;
    }
    div[role="radiogroup"][aria-label="Mode"] label {
        margin: 0 !important;
        padding: 0.4rem 1.2rem !important;
        border-bottom: 2px solid transparent;
        border-radius: 0 !important;
    }
    div[role="radiogroup"][aria-label="Mode"] label > div:first-child {
        display: none;
    }
    div[role="radiogroup"][aria-label="Mode"] label:has(input:checked) {
        border-bottom-color: #2563eb;
    }
    div[role="radiogroup"][aria-label="Mode"] label:has(input:checked) p {
        color: #2563eb !important;
        font-weight: 600;
    }
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


NON_GK_OPTION = "Non-Goalkeeper (all outfield)"


def is_goalkeeper_position(value):
    v = str(value).strip().lower()
    return "gk" in v or "keep" in v


def position_multiselect(label, positions_available, key):
    """Multiselect over `positions_available` plus a convenience option that
    expands to every non-goalkeeper position at once."""
    choice = st.multiselect(label, positions_available + [NON_GK_OPTION], key=key)
    if not choice:
        return None
    expanded = set()
    for p in choice:
        if p == NON_GK_OPTION:
            expanded.update(pos for pos in positions_available if not is_goalkeeper_position(pos))
        else:
            expanded.add(p)
    return list(expanded) if expanded else None


mode_label = st.radio("Mode", ["Team Stats", "Individual Stats"], horizontal=True, label_visibility="collapsed")
mode = "team" if mode_label == "Team Stats" else "individual"

upload_row = st.columns(2)
with upload_row[0]:
    uploaded = st.file_uploader(f"Upload {mode_label} CSV", type="csv", key="primary_csv")
with upload_row[1]:
    dataset_label = st.radio(
        "Dataset", ["General", "NCAA"], horizontal=True,
        help="General is dataset-agnostic for any "
        "team/player CSV. NCAA uses the built-in NCAA soccer stat presets.",
    )
    dataset = "ncaa" if dataset_label == "NCAA" else "general"

aliases_cfg = config_loader.load_aliases(dataset, mode)
stat_meta = aliases_cfg["stats"]
presets = config_loader.load_presets(dataset, mode)

if uploaded is None:
    st.info("Upload a CSV to get started.")
    st.stop()

df = data_io.load_csv(uploaded)

entity_col = stat_resolver.resolve_single(df, aliases_cfg.get("entity_column", []))
if entity_col is None:
    st.error("Could not find a name/team identity column in this CSV.")
    st.stop()

position_col = stat_resolver.resolve_single(df, aliases_cfg.get("position_column", []))

team_name_col = None
if mode == "individual":
    team_name_col = stat_resolver.resolve_single(df, aliases_cfg.get("team_column", ["Team"]))


def entity_display_label(name, idx):
    """Returns "Name (Team)" for individual-mode players when a team column
    is available; just the raw name otherwise (team mode, or "League Average")."""
    if team_name_col is None:
        return name
    return f"{name} ({df.loc[idx, team_name_col]})"

row1 = st.columns(3) if position_col else st.columns(2)
with row1[0]:
    filter_cols_chosen = st.multiselect("Exclude rows missing/zero in", list(df.columns))
    for fc in filter_cols_chosen:
        df = data_io.apply_missing_filter(df, fc)

position_filter = None
if position_col:
    with row1[1]:
        positions_available = sorted(df[position_col].dropna().unique().tolist())
        position_filter = position_multiselect(
            "Restrict baseline to positions", positions_available, key="baseline_position_filter"
        )
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

wheel_row = st.columns([3, 2])
with wheel_row[0]:
    st.plotly_chart(fig, use_container_width=True)
with wheel_row[1]:
    st.caption(entity_display_label(entity_name, entity_idx))
    st.dataframe(
        stat_table(active_stat_labels, entity_raw, entity_values),
        hide_index=True,
        use_container_width=True,
    )
    if compare_values is not None:
        compare_caption = (
            entity_display_label(compare_name, compare_idx)
            if comparison_mode == "Head-to-Head"
            else compare_name
        )
        st.caption(compare_caption)
        st.dataframe(
            stat_table(active_stat_labels, compare_raw, compare_values),
            hide_index=True,
            use_container_width=True,
        )

main_two_col = st.columns([3, 2])

with main_two_col[0]:
    st.subheader("Scatter Explorer")

    scatter_presets = config_loader.load_scatter_presets(dataset, mode)

    scatter_row = st.columns(4) if position_col else st.columns(3)
    with scatter_row[0]:
        scatter_preset_names = list(scatter_presets.keys()) + ["Custom"]
        scatter_preset_choice = st.selectbox("Scatter preset", scatter_preset_names, key="scatter_preset")

    scatter_position_filter = None
    if position_col:
        with scatter_row[1]:
            scatter_positions_available = sorted(df[position_col].dropna().unique().tolist())
            scatter_position_filter = position_multiselect(
                "Restrict scatter to positions", scatter_positions_available, key="scatter_position_filter"
            )
        extra_highlight_col = scatter_row[2]
        scatter_checkbox_col = scatter_row[3]
    else:
        extra_highlight_col = scatter_row[1]
        scatter_checkbox_col = scatter_row[2]

    with extra_highlight_col:
        extra_highlight_options = ["(none)"] + [e for e in entities if e not in {entity_name, compare_name}]
        extra_highlight_choice = st.selectbox(
            f"Highlight additional {entity_word.lower()}", extra_highlight_options, key="extra_highlight"
        )

    with scatter_checkbox_col:
        show_trend = st.checkbox("Show trend line", key="scatter_trend")
        show_avg_lines = st.checkbox("Show average lines", key="scatter_avg_lines")

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

    scatter_df = df
    if scatter_position_filter and position_col:
        scatter_df = scatter_df[scatter_df[position_col].isin(scatter_position_filter)]

    scatter_label_col = None
    if team_name_col:
        scatter_df = scatter_df.copy()
        scatter_label_col = "_display_label"
        scatter_df[scatter_label_col] = (
            scatter_df[entity_col].astype(str) + " (" + scatter_df[team_name_col].astype(str) + ")"
        )

    scatter_fig = None
    if scatter_resolved[scatter_x_canonical] and scatter_resolved[scatter_y_canonical]:
        scatter_x_col = scatter_resolved[scatter_x_canonical]
        scatter_y_col = scatter_resolved[scatter_y_canonical]
        scatter_x_numeric = pd.to_numeric(scatter_df[scatter_x_col], errors="coerce")
        scatter_y_numeric = pd.to_numeric(scatter_df[scatter_y_col], errors="coerce")
        scatter_overlap_count = int((scatter_x_numeric.notna() & scatter_y_numeric.notna()).sum())

        if scatter_overlap_count == 0:
            st.warning(
                "No rows have both stats at once — they may be mutually exclusive by position "
                "(e.g. one only applies to goalkeepers, the other only to outfield players). "
                "Try a different pair, or use the position filter above to narrow to compatible players."
            )
        else:
            scatter_highlight = [(entity_name, charts.PRIMARY_COLOR)]
            if comparison_mode == "Head-to-Head" and compare_values is not None:
                scatter_highlight.append((compare_name, charts.COMPARE_COLOR))
            if extra_highlight_choice != "(none)":
                scatter_highlight.append((extra_highlight_choice, charts.EXTRA_HIGHLIGHT_COLOR))

            scatter_fig = charts.build_scatter(
                scatter_df,
                scatter_x_col,
                scatter_y_col,
                stat_resolver.display_name(scatter_x_canonical),
                stat_resolver.display_name(scatter_y_canonical),
                entity_col,
                highlight=scatter_highlight,
                color_col=position_col,
                show_trend=show_trend,
                show_avg_lines=show_avg_lines,
                label_col=scatter_label_col,
            )

    if scatter_fig is not None:
        st.plotly_chart(scatter_fig, use_container_width=True)
    else:
        st.info("Pick valid columns for both scatter stats to render the plot.")

with main_two_col[1]:
    st.subheader("Extrema Finder")

    extrema_display_to_canonical = {}
    for canonical in stat_meta.keys():
        label = stat_resolver.display_name(canonical)
        if label in extrema_display_to_canonical:
            label = f"{label} ({canonical})"
        extrema_display_to_canonical[label] = canonical
    extrema_stat_display = st.selectbox(
        "Stat", sorted(extrema_display_to_canonical.keys()), key="extrema_stat"
    )
    extrema_canonical = extrema_display_to_canonical[extrema_stat_display]
    extrema_resolved = stat_resolver.resolve_stats(df, [extrema_canonical], stat_meta)
    extrema_col = extrema_resolved[extrema_canonical]

    if extrema_col is None:
        st.info("Stat not found in this CSV.")
    else:
        extrema_numeric = pd.to_numeric(scatter_df[extrema_col], errors="coerce")
        extrema_valid = scatter_df.loc[extrema_numeric.notna()].copy()
        extrema_valid["_extrema_value"] = extrema_numeric[extrema_numeric.notna()]

        if extrema_valid.empty:
            st.info("No valid values for this stat.")
        else:
            def extrema_table(rows_df):
                return pd.DataFrame(
                    {
                        entity_word: [
                            entity_display_label(rows_df.loc[i, entity_col], i) for i in rows_df.index
                        ],
                        "Value": rows_df["_extrema_value"].round(2).tolist(),
                    }
                )

            top5 = extrema_valid.nlargest(5, "_extrema_value")
            bottom5 = extrema_valid.nsmallest(5, "_extrema_value")

            st.caption(f"Top 5 — {extrema_stat_display}")
            st.dataframe(extrema_table(top5), hide_index=True, use_container_width=True)
            st.caption(f"Bottom 5 — {extrema_stat_display}")
            st.dataframe(extrema_table(bottom5), hide_index=True, use_container_width=True)
