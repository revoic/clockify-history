import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from collections import Counter
import re

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Clockify Insights",
    page_icon="⏱️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #2d6a9f 0%, #1e3a5f 100%);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        margin-bottom: 0.5rem;
    }
    .metric-card h3 { margin: 0; font-size: 0.85rem; opacity: 0.8; }
    .metric-card h1 { margin: 0; font-size: 2rem; font-weight: 700; }
    .metric-card p  { margin: 0; font-size: 0.75rem; opacity: 0.7; }
    .stTabs [data-baseweb="tab"] { font-size: 0.9rem; font-weight: 600; }
    h1, h2, h3 { color: #1e3a5f; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────
@st.cache_data
def load_data(path) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, low_memory=False)
    except Exception as e:
        st.error(f"Fehler beim Laden der Datei: {e}")
        st.stop()

    df.columns = df.columns.str.strip()

    col_map = {
        "Benutzer": "user", "User": "user", "Nutzer": "user",
        "Kunde": "client", "Client": "client",
        "Projekt": "project", "Project": "project",
        "Beschreibung": "description", "Description": "description",
        "Abrechenbar": "billable", "Billable": "billable",
        "Startdatum": "start_date", "Start Date": "start_date", "Datum": "start_date",
        "Startzeit": "start_time", "Start Time": "start_time",
        "Dauer (Dezimalzahl)": "duration_h", "Duration (decimal)": "duration_h",
        "Dauer (dezimal)": "duration_h", "Dauer (h)": "duration_h",
    }
    df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)

    if "duration_h" not in df.columns:
        for c in df.columns:
            if "dauer" in c.lower() or "duration" in c.lower():
                df.rename(columns={c: "duration_h"}, inplace=True)
                break

    # Dauer robust parsen – egal ob float, int oder String mit Komma
    raw_dur = df["duration_h"]
    if pd.api.types.is_numeric_dtype(raw_dur):
        df["duration_h"] = pd.to_numeric(raw_dur, errors="coerce").fillna(0)
    else:
        df["duration_h"] = (
            raw_dur.astype(str)
            .str.replace(",", ".", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0)
        )

    if "start_date" in df.columns:
        df["date"] = pd.to_datetime(df["start_date"], dayfirst=True, errors="coerce")
    else:
        df["date"] = pd.NaT

    df["year"]    = df["date"].dt.year
    df["month"]   = df["date"].dt.to_period("M").astype(str)
    df["quarter"] = df["date"].dt.to_period("Q").astype(str)
    df["weekday"] = df["date"].dt.day_name()

    if "start_time" in df.columns:
        df["hour"] = pd.to_datetime(
            df["start_time"].astype(str), format="%H:%M", errors="coerce"
        ).dt.hour
        mask = df["hour"].isna()
        df.loc[mask, "hour"] = pd.to_datetime(
            df.loc[mask, "start_time"].astype(str), format="%H:%M:%S", errors="coerce"
        ).dt.hour
    else:
        df["hour"] = df["date"].dt.hour

    if "billable" in df.columns:
        df["billable"] = df["billable"].astype(str).str.strip().str.lower()
        df["is_billable"] = df["billable"].isin(["ja", "yes", "true", "1", "wahr"])
    else:
        df["is_billable"] = False

    if "client" in df.columns:
        df["client"] = df["client"].fillna("Kein Kunde").astype(str).str.strip()
        internal_keywords = ["intern", "internal", "revoic", "eigene", "administration"]
        df["is_internal"] = df["client"].str.lower().str.contains(
            "|".join(internal_keywords), na=False
        )
    else:
        df["client"] = "Unbekannt"
        df["is_internal"] = False

    df["project"]     = df["project"].fillna("Kein Projekt").astype(str).str.strip() if "project" in df.columns else "Unbekannt"
    df["user"]        = df["user"].fillna("Unbekannt").astype(str).str.strip() if "user" in df.columns else "Unbekannt"
    df["description"] = df["description"].fillna("").astype(str) if "description" in df.columns else ""

    return df

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
st.sidebar.markdown("""
<div style="background: linear-gradient(135deg, #2d6a9f 0%, #1e3a5f 100%);
            padding: 16px 20px; border-radius: 12px; margin-bottom: 12px;">
    <span style="color:white; font-size:1.4rem; font-weight:700;">⏱️ Clockify Insights</span><br>
    <span style="color:rgba(255,255,255,0.7); font-size:0.75rem;">Zeiterfassung · Analyse · Überblick</span>
</div>
""", unsafe_allow_html=True)
st.sidebar.markdown("---")

uploaded = st.sidebar.file_uploader("📁 Clockify CSV hochladen", type=["csv"])

if not uploaded:
    st.markdown("## ⏱️ Clockify Insights")
    st.info(
        "👆 Bitte lade in der **Sidebar links** eine Clockify-CSV-Datei hoch.\n\n"
        "**Export-Weg in Clockify:** Berichte → Detailliert → CSV exportieren"
    )
    st.stop()

df_raw = load_data(uploaded)

st.sidebar.markdown("### 🔍 Filter")

years = sorted(df_raw["year"].dropna().unique().astype(int).tolist())
sel_years = st.sidebar.multiselect("Jahr(e)", years, default=years)

all_users = sorted(df_raw["user"].unique().tolist())
sel_users = st.sidebar.multiselect("Mitarbeiter:in", all_users, default=all_users)

all_clients = sorted(df_raw["client"].unique().tolist())
sel_clients = st.sidebar.multiselect("Kunde", all_clients, default=all_clients)

granularity = st.sidebar.radio("Zeitgranularität", ["Monat", "Quartal", "Jahr"], index=0)
gran_col = {"Monat": "month", "Quartal": "quarter", "Jahr": "year"}[granularity]

st.sidebar.markdown("---")
st.sidebar.caption(f"📊 {len(df_raw):,} Einträge geladen")

df = df_raw[
    df_raw["year"].isin(sel_years) &
    df_raw["user"].isin(sel_users) &
    df_raw["client"].isin(sel_clients)
].copy()

if df.empty:
    st.warning("Keine Daten für die gewählten Filter. Bitte Filter anpassen.")
    st.stop()

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
st.markdown("# ⏱️ Clockify Insights")
st.markdown(
    f"**{len(df):,} Einträge** · "
    f"{df['user'].nunique()} Personen · "
    f"{df['client'].nunique()} Kunden · "
    f"{df['project'].nunique()} Projekte · "
    f"{df['date'].min().strftime('%d.%m.%Y') if pd.notna(df['date'].min()) else '?'} – "
    f"{df['date'].max().strftime('%d.%m.%Y') if pd.notna(df['date'].max()) else '?'}"
)
st.markdown("---")

# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tabs = st.tabs([
    "📊 Überblick",
    "📈 Entwicklung",
    "👥 Team",
    "🏢 Kunden",
    "🗂️ Projekte",
    "🔄 Intern vs. Extern",
    "🎉 Fun Facts",
])

PALETTE = px.colors.qualitative.Bold

# ══════════════════════════════════════════════
# TAB 1 – ÜBERBLICK
# ══════════════════════════════════════════════
with tabs[0]:
    total_h   = df["duration_h"].sum()
    avg_entry = df["duration_h"].mean()
    pct_bill  = df["is_billable"].mean() * 100
    pct_int   = df["is_internal"].mean() * 100
    n_clients = df["client"].nunique()

    c1, c2, c3, c4, c5 = st.columns(5)
    for col, label, value, sub in zip(
        [c1, c2, c3, c4, c5],
        ["⏱️ Gesamt-Stunden", "⌀ pro Buchung (min)", "✅ Abrechenbar", "🏠 Intern", "🏢 Kunden"],
        [f"{total_h:,.0f} h", f"{avg_entry*60:.0f} min", f"{pct_bill:.1f} %", f"{pct_int:.1f} %", str(n_clients)],
        ["Alle gefilterten Einträge", "Durchschnittliche Buchungslänge", "Anteil abrechenbarer Zeit",
         "Anteil interner Buchungen", "Einzigartige Kunden"],
    ):
        col.markdown(
            f'<div class="metric-card"><h3>{label}</h3><h1>{value}</h1><p>{sub}</p></div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Stunden pro Jahr")
        by_year = df.groupby("year")["duration_h"].sum().reset_index()
        fig = px.bar(by_year, x="year", y="duration_h", color="year",
                     color_discrete_sequence=PALETTE,
                     labels={"duration_h": "Stunden", "year": "Jahr"},
                     text_auto=".0f")
        fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Top 10 Kunden")
        top_clients = (
            df.groupby("client")["duration_h"].sum()
            .sort_values(ascending=True).tail(10).reset_index()
        )
        fig = px.bar(top_clients, x="duration_h", y="client", orientation="h",
                     color="duration_h", color_continuous_scale="Blues",
                     labels={"duration_h": "Stunden", "client": "Kunde"},
                     text_auto=".0f")
        fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    col_l2, col_r2 = st.columns(2)
    with col_l2:
        st.subheader("Top 10 Projekte")
        top_proj = (
            df.groupby("project")["duration_h"].sum()
            .sort_values(ascending=True).tail(10).reset_index()
        )
        fig = px.bar(top_proj, x="duration_h", y="project", orientation="h",
                     color="duration_h", color_continuous_scale="Teal",
                     labels={"duration_h": "Stunden", "project": "Projekt"},
                     text_auto=".0f")
        fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col_r2:
        st.subheader("Abrechenbar vs. Nicht-Abrechenbar")
        bill_data = df.groupby("is_billable")["duration_h"].sum().reset_index()
        bill_data["label"] = bill_data["is_billable"].map({True: "Abrechenbar", False: "Nicht-Abrechenbar"})
        fig = px.pie(bill_data, values="duration_h", names="label",
                     color_discrete_sequence=["#2d6a9f", "#e8b04b"],
                     hole=0.45)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════
# TAB 2 – ENTWICKLUNG
# ══════════════════════════════════════════════
with tabs[1]:
    st.subheader(f"Stundenentwicklung ({granularity})")

    ts = df.groupby(gran_col)["duration_h"].sum().reset_index().sort_values(gran_col)
    fig = px.line(ts, x=gran_col, y="duration_h", markers=True,
                  labels={"duration_h": "Stunden", gran_col: granularity},
                  color_discrete_sequence=["#2d6a9f"])
    fig.update_traces(line_width=2.5, marker_size=7)
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Abrechenbar vs. Nicht-Abrechenbar im Verlauf")
        ts_bill = (
            df.groupby([gran_col, "is_billable"])["duration_h"].sum()
            .reset_index().sort_values(gran_col)
        )
        ts_bill["Typ"] = ts_bill["is_billable"].map({True: "Abrechenbar", False: "Nicht-Abrechenbar"})
        fig = px.area(ts_bill, x=gran_col, y="duration_h", color="Typ",
                      color_discrete_sequence=["#2d6a9f", "#e8b04b"],
                      labels={"duration_h": "Stunden", gran_col: granularity})
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("% Abrechenbar – Effizienztrend")
        ts_pct = (
            df.groupby(gran_col)
            .apply(lambda x: x["is_billable"].mean() * 100, include_groups=False)
            .reset_index(name="pct_billable")
            .sort_values(gran_col)
        )
        fig = px.line(ts_pct, x=gran_col, y="pct_billable", markers=True,
                      color_discrete_sequence=["#27ae60"],
                      labels={"pct_billable": "% Abrechenbar", gran_col: granularity})
        fig.add_hline(y=ts_pct["pct_billable"].mean(), line_dash="dash",
                      line_color="gray", annotation_text="Ø Gesamt")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Neue Kunden pro Jahr")
    first_year = (
        df.groupby("client")["year"].min().reset_index()
        .rename(columns={"year": "first_year"})
    )
    new_per_year = first_year.groupby("first_year").size().reset_index(name="neue_kunden")
    fig = px.bar(new_per_year, x="first_year", y="neue_kunden",
                 color_discrete_sequence=["#8e44ad"], text_auto=True,
                 labels={"first_year": "Jahr", "neue_kunden": "Neue Kunden"})
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════
# TAB 3 – TEAM
# ══════════════════════════════════════════════
with tabs[2]:
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Stunden pro Person")
        by_user = (
            df.groupby("user")["duration_h"].sum()
            .sort_values(ascending=True).reset_index()
        )
        fig = px.bar(by_user, x="duration_h", y="user", orientation="h",
                     color="duration_h", color_continuous_scale="Blues",
                     labels={"duration_h": "Stunden", "user": "Person"},
                     text_auto=".0f")
        fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)",
                          height=max(400, len(by_user) * 28))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("% Abrechenbar pro Person")
        bill_user = (
            df.groupby("user")
            .apply(lambda x: x["is_billable"].mean() * 100, include_groups=False)
            .reset_index(name="pct")
            .sort_values("pct", ascending=True)
        )
        bill_user["color"] = bill_user["pct"].apply(
            lambda v: "#27ae60" if v >= 60 else ("#e8b04b" if v >= 30 else "#e74c3c")
        )
        fig = px.bar(bill_user, x="pct", y="user", orientation="h",
                     color="color", color_discrete_map="identity",
                     labels={"pct": "% Abrechenbar", "user": "Person"},
                     text_auto=".1f")
        fig.add_vline(x=60, line_dash="dash", line_color="gray",
                      annotation_text="60 % Ziel")
        fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                          height=max(400, len(bill_user) * 28))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader(f"Top-10-Personen im Zeitverlauf ({granularity})")
    top10_users = (
        df.groupby("user")["duration_h"].sum()
        .sort_values(ascending=False).head(10).index.tolist()
    )
    ts_user = (
        df[df["user"].isin(top10_users)]
        .groupby([gran_col, "user"])["duration_h"].sum()
        .reset_index().sort_values(gran_col)
    )
    fig = px.line(ts_user, x=gran_col, y="duration_h", color="user",
                  color_discrete_sequence=PALETTE, markers=False,
                  labels={"duration_h": "Stunden", gran_col: granularity, "user": "Person"})
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Heatmap: Buchungen nach Wochentag & Person")
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    heatmap_data = (
        df.groupby(["user", "weekday"])["duration_h"].sum()
        .reset_index()
        .pivot(index="user", columns="weekday", values="duration_h")
        .reindex(columns=[d for d in weekday_order if d in df["weekday"].unique()])
        .fillna(0)
    )
    fig = px.imshow(heatmap_data, color_continuous_scale="Blues",
                    labels={"color": "Stunden"}, aspect="auto")
    fig.update_layout(height=max(400, len(heatmap_data) * 30))
    st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════
# TAB 4 – KUNDEN
# ══════════════════════════════════════════════
with tabs[3]:
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Top-12-Kunden im Zeitverlauf")
        top12_clients = (
            df.groupby("client")["duration_h"].sum()
            .sort_values(ascending=False).head(12).index.tolist()
        )
        ts_cl = (
            df[df["client"].isin(top12_clients)]
            .groupby([gran_col, "client"])["duration_h"].sum()
            .reset_index().sort_values(gran_col)
        )
        fig = px.line(ts_cl, x=gran_col, y="duration_h", color="client",
                      color_discrete_sequence=PALETTE, markers=False,
                      labels={"duration_h": "Stunden", gran_col: granularity, "client": "Kunde"})
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Kundenlaufzeit vs. Gesamtstunden")
        client_stats = df.groupby("client").agg(
            total_h=("duration_h", "sum"),
            first_date=("date", "min"),
            last_date=("date", "max"),
        ).reset_index()
        client_stats["laufzeit_tage"] = (
            client_stats["last_date"] - client_stats["first_date"]
        ).dt.days
        fig = px.scatter(
            client_stats, x="laufzeit_tage", y="total_h", text="client",
            color="total_h", color_continuous_scale="Blues", size="total_h",
            labels={"laufzeit_tage": "Laufzeit (Tage)", "total_h": "Gesamtstunden"},
            size_max=40,
        )
        fig.update_traces(textposition="top center")
        fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Alle Kunden – Übersicht")
    client_table = df.groupby("client").agg(
        Stunden=("duration_h", "sum"),
        Buchungen=("duration_h", "count"),
        Projekte=("project", "nunique"),
        Personen=("user", "nunique"),
        Erster_Eintrag=("date", "min"),
        Letzter_Eintrag=("date", "max"),
    ).reset_index().sort_values("Stunden", ascending=False)
    client_table["Stunden"] = client_table["Stunden"].round(1)
    client_table["Erster_Eintrag"] = client_table["Erster_Eintrag"].dt.strftime("%d.%m.%Y")
    client_table["Letzter_Eintrag"] = client_table["Letzter_Eintrag"].dt.strftime("%d.%m.%Y")
    st.dataframe(client_table, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🔎 Einzelkunden-Analyse")
    sel_client = st.selectbox("Kunde wählen", sorted(df["client"].unique()))
    dfc = df[df["client"] == sel_client]

    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown(f"**Projektmix für {sel_client}**")
        proj_mix = dfc.groupby("project")["duration_h"].sum().reset_index()
        fig = px.pie(proj_mix, values="duration_h", names="project",
                     color_discrete_sequence=PALETTE, hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    with cc2:
        st.markdown(f"**Monatsverlauf für {sel_client}**")
        ts_c = dfc.groupby("month")["duration_h"].sum().reset_index().sort_values("month")
        fig = px.bar(ts_c, x="month", y="duration_h",
                     color_discrete_sequence=["#2d6a9f"],
                     labels={"duration_h": "Stunden", "month": "Monat"})
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════
# TAB 5 – PROJEKTE
# ══════════════════════════════════════════════
with tabs[4]:
    st.subheader(f"Projektmix-Anteil im Zeitverlauf ({granularity})")
    top15_proj = (
        df.groupby("project")["duration_h"].sum()
        .sort_values(ascending=False).head(15).index.tolist()
    )
    ts_proj = (
        df[df["project"].isin(top15_proj)]
        .groupby([gran_col, "project"])["duration_h"].sum()
        .reset_index().sort_values(gran_col)
    )
    totals = ts_proj.groupby(gran_col)["duration_h"].sum().rename("total")
    ts_proj = ts_proj.join(totals, on=gran_col)
    ts_proj["anteil"] = ts_proj["duration_h"] / ts_proj["total"] * 100

    fig = px.area(ts_proj, x=gran_col, y="anteil", color="project",
                  color_discrete_sequence=PALETTE,
                  labels={"anteil": "Anteil (%)", gran_col: granularity, "project": "Projekt"},
                  groupnorm="")
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", height=500)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Alle Projekte – Übersicht")
    proj_table = df.groupby(["project", "client"]).agg(
        Stunden=("duration_h", "sum"),
        Buchungen=("duration_h", "count"),
        Personen=("user", "nunique"),
        Erster_Eintrag=("date", "min"),
        Letzter_Eintrag=("date", "max"),
    ).reset_index().sort_values("Stunden", ascending=False)
    proj_table["Stunden"] = proj_table["Stunden"].round(1)
    proj_table["Erster_Eintrag"] = proj_table["Erster_Eintrag"].dt.strftime("%d.%m.%Y")
    proj_table["Letzter_Eintrag"] = proj_table["Letzter_Eintrag"].dt.strftime("%d.%m.%Y")
    st.dataframe(proj_table, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════
# TAB 6 – INTERN VS. EXTERN
# ══════════════════════════════════════════════
with tabs[5]:
    st.subheader(f"Intern vs. Kunden-Zeit ({granularity})")
    df["typ"] = df["is_internal"].map({True: "Intern", False: "Kunden"})
    ts_int = (
        df.groupby([gran_col, "typ"])["duration_h"].sum()
        .reset_index().sort_values(gran_col)
    )
    fig = px.area(ts_int, x=gran_col, y="duration_h", color="typ",
                  color_discrete_sequence=["#e8b04b", "#2d6a9f"],
                  labels={"duration_h": "Stunden", gran_col: granularity, "typ": "Typ"})
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("% Interne Zeit pro Periode")
        pct_int_ts = (
            df.groupby(gran_col)
            .apply(lambda x: x["is_internal"].mean() * 100, include_groups=False)
            .reset_index(name="pct_intern")
            .sort_values(gran_col)
        )
        fig = px.line(pct_int_ts, x=gran_col, y="pct_intern", markers=True,
                      color_discrete_sequence=["#e8b04b"],
                      labels={"pct_intern": "% Intern", gran_col: granularity})
        fig.add_hline(y=pct_int_ts["pct_intern"].mean(), line_dash="dash",
                      line_color="gray", annotation_text="Ø")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Interner Projektmix")
        int_proj = (
            df[df["is_internal"]]
            .groupby("project")["duration_h"].sum()
            .sort_values(ascending=False).head(12).reset_index()
        )
        if int_proj.empty:
            st.info("Keine internen Buchungen gefunden. Prüfe den Kundennamen (Stichwort: 'intern', 'internal' oder Firmenname).")
        else:
            fig = px.pie(int_proj, values="duration_h", names="project",
                         color_discrete_sequence=PALETTE, hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════
# TAB 7 – FUN FACTS
# ══════════════════════════════════════════════
with tabs[6]:
    st.subheader("🎉 Fun Facts & Kuriositäten")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 🌅 Frühaufsteher")
        if "hour" in df.columns and df["hour"].notna().any():
            early = df[df["hour"] < 7]
            if not early.empty:
                top_early = early.groupby("user")["duration_h"].count().idxmax()
                st.metric("Buchungen vor 7 Uhr", early.shape[0])
                st.metric("Fleißigste Frühaufsteherin", top_early)
            else:
                st.info("Keine Buchungen vor 7 Uhr.")
        else:
            st.info("Keine Zeitdaten verfügbar.")

    with col2:
        st.markdown("### 🦉 Nachteulen")
        if "hour" in df.columns and df["hour"].notna().any():
            late = df[df["hour"] >= 21]
            if not late.empty:
                top_late = late.groupby("user")["duration_h"].count().idxmax()
                st.metric("Buchungen ab 21 Uhr", late.shape[0])
                st.metric("Fleißigste Nachteule", top_late)
            else:
                st.info("Keine Buchungen ab 21 Uhr.")
        else:
            st.info("Keine Zeitdaten verfügbar.")

    with col3:
        st.markdown("### 🏋️ Wochenend-Warriors")
        weekend = df[df["weekday"].isin(["Saturday", "Sunday"])]
        if not weekend.empty:
            top_wknd = weekend.groupby("user")["duration_h"].sum().idxmax()
            h_wknd   = weekend["duration_h"].sum()
            st.metric("Wochenend-Stunden gesamt", f"{h_wknd:.0f} h")
            st.metric("Wochenend-Champion", top_wknd)
        else:
            st.info("Keine Wochenend-Buchungen.")

    st.markdown("---")
    col4, col5 = st.columns(2)

    with col4:
        st.markdown("### ⚡ Kürzeste & längste Buchung")
        pos_df = df[df["duration_h"] > 0]
        if not pos_df.empty and pos_df["duration_h"].notna().any():
            shortest = df.loc[pos_df["duration_h"].idxmin()]
            st.info(
                f"**Kürzeste:** {shortest['duration_h']*60:.1f} min  \n"
                f"Person: {shortest['user']}  \n"
                f"Projekt: {shortest['project']}"
            )
        else:
            st.info("Keine positiven Buchungen vorhanden.")

        all_df = df[df["duration_h"].notna()]
        if not all_df.empty:
            longest = df.loc[all_df["duration_h"].idxmax()]
            st.success(
                f"**Längste:** {longest['duration_h']:.1f} h  \n"
                f"Person: {longest['user']}  \n"
                f"Projekt: {longest['project']}"
            )

        st.markdown("### 🏆 Produktivster Tag")
        day_series = df.groupby(df["date"].dt.date)["duration_h"].sum()
        if not day_series.empty:
            best_day = day_series.idxmax()
            best_h   = day_series.max()
            st.success(f"**{best_day}** mit {best_h:.0f} Stunden im Team")
        else:
            st.info("Keine Tagesdaten verfügbar.")

    with col5:
        st.markdown("### 🕐 Buchungen nach Tageszeit")
        if "hour" in df.columns and df["hour"].notna().any():
            hour_dist = df.groupby("hour")["duration_h"].count().reset_index(name="buchungen")
            fig = px.bar(hour_dist, x="hour", y="buchungen",
                         color="buchungen", color_continuous_scale="Blues",
                         labels={"hour": "Uhrzeit", "buchungen": "Anzahl Buchungen"})
            fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Keine Uhrzeitdaten verfügbar.")

    st.markdown("---")
    st.markdown("### 💬 Häufigste Wörter in Beschreibungen")
    all_text = " ".join(df["description"].astype(str).tolist()).lower()
    stopwords = {
        "und", "der", "die", "das", "für", "mit", "an", "auf", "in", "zu",
        "von", "bei", "ist", "im", "am", "ein", "eine", "einer", "einen",
        "des", "dem", "den", "ich", "wir", "sie", "es", "er", "hat", "haben",
        "the", "and", "for", "with", "of", "to", "a", "on", "is",
        "nan", "", "-", "–",
    }
    words = re.findall(r"\b[a-zäöüß]{3,}\b", all_text)
    word_freq = Counter(w for w in words if w not in stopwords)
    top_words = pd.DataFrame(word_freq.most_common(30), columns=["Wort", "Häufigkeit"])
    fig = px.bar(top_words.sort_values("Häufigkeit"), x="Häufigkeit", y="Wort",
                 orientation="h", color="Häufigkeit", color_continuous_scale="Blues",
                 text_auto=True)
    fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)", height=600)
    st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.markdown("---")
st.caption("⏱️ Clockify Insights · Gebaut mit Streamlit & Plotly · Daten aus Clockify CSV-Export")
