import pandas as pd
import streamlit as st

from src import charts, config_loader, data_io, percentiles, stat_resolver

st.set_page_config(page_title="NCAA Soccer Stat Wheel", layout="wide")
st.title("NCAA Soccer Stat Wheel")

mode_label = st.radio("Mode", ["Team Stats", "Individual Stats"], horizontal=True)
mode = "team" if mode_label == "Team Stats" else "individual"

aliases_cfg = config_loader.load_aliases(mode)
stat_meta = aliases_cfg["stats"]
presets = config_loader.load_presets(mode)

uploaded = st.file_uploader(f"Upload {mode_label} CSV", type="csv", key="primary_csv")

team_csv_df = None
if mode == "individual":
    team_upload = st.file_uploader(
        "Optional: Team Stats CSV (to cross-reference a player's team)",
        type="csv",
        key="team_csv",
    )
    if team_upload is not None:
        team_csv_df = data_io.load_csv(team_upload)

if uploaded is None:
    st.info("Upload a CSV to get started.")
    st.stop()

df = data_io.load_csv(uploaded)

entity_col = stat_resolver.resolve_single(df, aliases_cfg.get("entity_column", []))
if entity_col is None:
    st.error("Could not find a name/team identity column in this CSV.")
    st.stop()

st.subheader("Filter")
filter_col = st.selectbox(
    "Exclude rows missing/zero in column (optional)", ["(none)"] + list(df.columns)
)
if filter_col != "(none)":
    df = data_io.apply_missing_filter(df, filter_col)

position_col = stat_resolver.resolve_single(df, aliases_cfg.get("position_column", []))
position_filter = None
if position_col:
    positions_available = sorted(df[position_col].dropna().unique().tolist())
    position_filter = st.multiselect(
        "Restrict percentile baseline to positions (optional)", positions_available
    )
    if not position_filter:
        position_filter = None

st.subheader("Stats")
preset_names = list(presets.keys()) + ["Custom"]
preset_choice = st.selectbox("Preset", preset_names)
if preset_choice == "Custom":
    canonical_stats = st.multiselect(
        "Pick exactly 6 stats", list(stat_meta.keys()), max_selections=6
    )
    if len(canonical_stats) != 6:
        st.warning("Pick exactly 6 stats to continue.")
        st.stop()
else:
    canonical_stats = presets[preset_choice]

resolved = stat_resolver.resolve_stats(df, canonical_stats, stat_meta)

unresolved = [s for s, col in resolved.items() if col is None]
if unresolved:
    st.warning("Some preset stats weren't found automatically — pick their columns below:")
    for stat in unresolved:
        choice = st.selectbox(
            f"Column for '{stat}'", ["(skip)"] + list(df.columns), key=f"resolve_{mode}_{stat}"
        )
        resolved[stat] = None if choice == "(skip)" else choice

active_stats = [s for s in canonical_stats if resolved.get(s)]
if not active_stats:
    st.error("No stats resolved — cannot build a chart.")
    st.stop()

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


st.subheader("Comparison")
comparison_mode = st.radio("Comparison mode", ["Vs League Average", "Head-to-Head"], horizontal=True)
chart_kind = st.radio("Chart type", ["Wedges (bar_polar)", "Radar (line_polar)"], horizontal=True)
kind = "bar_polar" if chart_kind.startswith("Wedges") else "line_polar"

entity_name = st.selectbox("Entity", entities)
entity_idx = df[df[entity_col] == entity_name].index[0]
entity_values = get_values(entity_idx)
entity_raw = get_raw(entity_idx)

compare_values = compare_raw = compare_name = None
if comparison_mode == "Vs League Average":
    baseline = df.loc[pct_df.index]
    compare_values = [50] * len(active_stats)
    compare_raw = [
        pd.to_numeric(baseline[resolved[s]], errors="coerce").mean() for s in active_stats
    ]
    compare_name = "League Average"
else:
    other_entities = [e for e in entities if e != entity_name]
    if not other_entities:
        st.warning("No other entity available to compare against.")
    else:
        compare_entity = st.selectbox("Compare against", other_entities)
        compare_idx = df[df[entity_col] == compare_entity].index[0]
        compare_values = get_values(compare_idx)
        compare_raw = get_raw(compare_idx)
        compare_name = compare_entity

fig = charts.build_wheel(
    active_stats,
    entity_values,
    entity_name,
    raw_values=entity_raw,
    compare_values=compare_values,
    compare_name=compare_name,
    compare_raw=compare_raw,
    kind=kind,
)
st.plotly_chart(fig, use_container_width=True)

if mode == "individual" and team_csv_df is not None:
    team_aliases_cfg = config_loader.load_aliases("team")
    team_stat_meta = team_aliases_cfg["stats"]
    team_presets = config_loader.load_presets("team")
    team_entity_col = stat_resolver.resolve_single(team_csv_df, team_aliases_cfg.get("entity_column", []))
    player_team_col = stat_resolver.resolve_single(df, ["Team"])

    if team_entity_col and player_team_col:
        player_team_name = df.loc[entity_idx, player_team_col]
        match = team_csv_df[
            team_csv_df[team_entity_col].astype(str).str.strip() == str(player_team_name).strip()
        ]
        if not match.empty:
            st.subheader(f"{player_team_name} — Team Stats")
            team_preset_choice = st.selectbox(
                "Team preset", list(team_presets.keys()), key="team_preset"
            )
            team_canonical = team_presets[team_preset_choice]
            team_resolved = stat_resolver.resolve_stats(team_csv_df, team_canonical, team_stat_meta)
            team_active = [s for s in team_canonical if team_resolved.get(s)]
            if team_active:
                team_pct_df = percentiles.compute_percentiles(
                    team_csv_df, {s: team_resolved[s] for s in team_active}, team_stat_meta
                )
                team_idx = match.index[0]
                t_values = [
                    team_pct_df.loc[team_idx, s] if team_idx in team_pct_df.index else None
                    for s in team_active
                ]
                t_raw = [team_csv_df.loc[team_idx, team_resolved[s]] for s in team_active]
                team_fig = charts.build_wheel(
                    team_active,
                    t_values,
                    player_team_name,
                    raw_values=t_raw,
                    compare_values=[50] * len(team_active),
                    compare_name="League Average",
                    kind=kind,
                )
                st.plotly_chart(team_fig, use_container_width=True)
        else:
            st.caption(f"No matching team found in the uploaded team CSV for '{player_team_name}'.")
