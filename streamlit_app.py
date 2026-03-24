import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from collections import Counter
import re

st.set_page_config(page_title="Clockify Insights", page_icon="⏱️", layout="wide")

st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #2d6a9f 0%, #1e3a5f 100%);
        color: white; padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 0.5rem;
    }
    .metric-card h3 { margin: 0; font-size: 0.85rem; opacity: 0.8; }
    .metric-card h1 { margin: 0; font-size: 2rem; font-weight: 700; }
    .metric-card p  { margin: 0; font-size: 0.75rem; opacity: 0.7; }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data(f) -> pd.DataFrame:
    try:
        df = pd.read_csv(f, low_memory=False)
    except Exception as e:
        st.error(f"CSV konnte nicht geladen werden: {e}")
        st.stop()

    df.columns = df.columns.str.strip()

    # ── Spalten umbenennen ──────────────────────────────────────────────────
    rename = {
        "Benutzer": "user", "User": "user", "Nutzer": "user",
        "Kunde": "client", "Client": "client",
        "Projekt": "project", "Project": "project",
        "Beschreibung": "description", "Description": "description",
        "Abrechenbar": "billable", "Billable": "billable",
        "Startdatum": "start_date", "Start Date": "start_date", "Datum": "start_date",
        "Startzeit": "start_time", "Start Time": "start_time",
        "Dauer (dezimal)": "duration_h",
        "Dauer (Dezimalzahl)": "duration_h",
        "Duration (decimal)": "duration_h",
        "Dauer (h)": "duration_h",
    }
    df.rename(columns={k: v for k, v in rename.items() if k in df.columns}, inplace=True)

    # Fallback: erste Spalte mit "dauer" oder "duration"
    if "duration_h" not in df.columns:
        for c in df.columns:
            if "dauer" in c.lower() or "duration" in c.lower():
                df.rename(columns={c: "duration_h"}, inplace=True)
                break

    # ── Doppelte Spalten entfernen ──────────────────────────────────────────
    # (passiert wenn z.B. "Dauer (dezimal)" UND "Dauer (h)" beide zu duration_h werden)
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    # ── Dauer parsen ────────────────────────────────────────────────────────
    if "duration_h" in df.columns:
        col = df["duration_h"].squeeze()  # DataFrame → Series falls doppelt
        result = pd.to_numeric(col, errors="coerce")
        # Falls alles NaN: Spalte ist als String mit Komma gespeichert
        if result.isna().mean() > 0.9:
            result = pd.to_numeric(
                col.astype(str).str.strip().str.replace(",", ".", regex=False),
                errors="coerce"
            )
        df["duration_h"] = result.fillna(0.0)
    else:
        df["duration_h"] = 0.0

    # ── Datum / Zeit ────────────────────────────────────────────────────────
    df["date"] = pd.to_datetime(
        df.get("start_date", pd.Series(dtype=str)), dayfirst=True, errors="coerce"
    )
    df["year"]    = df["date"].dt.year
    df["month"]   = df["date"].dt.to_period("M").astype(str)
    df["quarter"] = df["date"].dt.to_period("Q").astype(str)
    df["weekday"] = df["date"].dt.day_name()

    if "start_time" in df.columns:
        t = df["start_time"].astype(str)
        df["hour"] = pd.to_datetime(t, format="%H:%M", errors="coerce").dt.hour
        mask = df["hour"].isna()
        df.loc[mask, "hour"] = pd.to_datetime(
            t[mask], format="%H:%M:%S", errors="coerce"
        ).dt.hour
    else:
        df["hour"] = df["date"].dt.hour

    # ── Flags ───────────────────────────────────────────────────────────────
    if "billable" in df.columns:
        df["is_billable"] = (
            df["billable"].astype(str).str.strip().str.lower()
            .isin(["ja", "yes", "true", "1", "wahr"])
        )
    else:
        df["is_billable"] = False

    df["client"] = df.get("client", pd.Series("Unbekannt", index=df.index))
    df["client"] = df["client"].fillna("Kein Kunde").astype(str).str.strip()
    df["is_internal"] = df["client"].str.lower().str.contains(
        "revoic|intern|internal|eigene|administration", na=False
    )

    df["project"]     = df.get("project", pd.Series("Unbekannt", index=df.index))
    df["project"]     = df["project"].fillna("Kein Projekt").astype(str).str.strip()
    df["user"]        = df.get("user", pd.Series("Unbekannt", index=df.index))
    df["user"]        = df["user"].fillna("Unbekannt").astype(str).str.strip()
    df["description"] = df.get("description", pd.Series("", index=df.index))
    df["description"] = df["description"].fillna("").astype(str)

    return df


# ── SIDEBAR ─────────────────────────────────────────────────────────────────
st.sidebar.markdown("""
<div style="background:linear-gradient(135deg,#2d6a9f,#1e3a5f);
            padding:16px 20px;border-radius:12px;margin-bottom:12px;">
  <span style="color:white;font-size:1.3rem;font-weight:700;">⏱️ Clockify Insights</span><br>
  <span style="color:rgba(255,255,255,0.7);font-size:0.75rem;">Zeiterfassung · Analyse · Überblick</span>
</div>
""", unsafe_allow_html=True)
st.sidebar.markdown("---")

uploaded = st.sidebar.file_uploader("📁 Clockify CSV hochladen", type=["csv"])
if not uploaded:
    st.info("👆 Bitte lade links in der Sidebar eine **Clockify CSV** hoch.\n\n"
            "**Clockify → Berichte → Detailliert → CSV exportieren**")
    st.stop()

df_raw = load_data(uploaded)

st.sidebar.markdown("### 🔍 Filter")
years      = sorted(df_raw["year"].dropna().unique().astype(int).tolist())
sel_years  = st.sidebar.multiselect("Jahr(e)", years, default=years)
sel_users  = st.sidebar.multiselect("Mitarbeiter:in", sorted(df_raw["user"].unique()), default=sorted(df_raw["user"].unique()))
sel_clients= st.sidebar.multiselect("Kunde", sorted(df_raw["client"].unique()), default=sorted(df_raw["client"].unique()))
gran       = st.sidebar.radio("Zeitgranularität", ["Monat", "Quartal", "Jahr"], index=0)
gc         = {"Monat": "month", "Quartal": "quarter", "Jahr": "year"}[gran]
st.sidebar.markdown("---")
st.sidebar.caption(f"📊 {len(df_raw):,} Einträge geladen")

df = df_raw[
    df_raw["year"].isin(sel_years) &
    df_raw["user"].isin(sel_users) &
    df_raw["client"].isin(sel_clients)
].copy()

if df.empty:
    st.warning("Keine Daten für diese Filterauswahl.")
    st.stop()

# ── HEADER ───────────────────────────────────────────────────────────────────
st.markdown("# ⏱️ Clockify Insights")
d_min = df["date"].min()
d_max = df["date"].max()
st.markdown(
    f"**{len(df):,} Einträge** · {df['user'].nunique()} Personen · "
    f"{df['client'].nunique()} Kunden · {df['project'].nunique()} Projekte · "
    f"{d_min.strftime('%d.%m.%Y') if pd.notna(d_min) else '?'} – "
    f"{d_max.strftime('%d.%m.%Y') if pd.notna(d_max) else '?'}"
)
st.markdown("---")

PAL = px.colors.qualitative.Bold
tabs = st.tabs(["📊 Überblick","📈 Entwicklung","👥 Team","🏢 Kunden","🗂️ Projekte","🔄 Intern vs. Extern","🎉 Fun Facts"])

# ════════════════════════════════════════════════════════════
# TAB 1 – ÜBERBLICK
# ════════════════════════════════════════════════════════════
with tabs[0]:
    c1,c2,c3,c4,c5 = st.columns(5)
    for col, lbl, val, sub in zip(
        [c1,c2,c3,c4,c5],
        ["⏱️ Gesamt-Stunden","⌀ Buchung (min)","✅ Abrechenbar","🏠 Intern","🏢 Kunden"],
        [f"{df['duration_h'].sum():,.0f} h",
         f"{df['duration_h'].mean()*60:.0f} min",
         f"{df['is_billable'].mean()*100:.1f} %",
         f"{df['is_internal'].mean()*100:.1f} %",
         str(df['client'].nunique())],
        ["Alle Einträge","Ø Buchungslänge","Abrechenbar","Intern (REVOIC)","Einzigartige Kunden"]
    ):
        col.markdown(
            f'<div class="metric-card"><h3>{lbl}</h3><h1>{val}</h1><p>{sub}</p></div>',
            unsafe_allow_html=True)

    st.markdown("---")
    l, r = st.columns(2)
    with l:
        st.subheader("Stunden pro Jahr")
        fig = px.bar(df.groupby("year")["duration_h"].sum().reset_index(),
                     x="year", y="duration_h", color="year",
                     color_discrete_sequence=PAL, text_auto=".0f",
                     labels={"duration_h":"Stunden","year":"Jahr"})
        fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with r:
        st.subheader("Top 10 Kunden")
        top = df.groupby("client")["duration_h"].sum().nlargest(10).sort_values().reset_index()
        fig = px.bar(top, x="duration_h", y="client", orientation="h",
                     color="duration_h", color_continuous_scale="Blues",
                     text_auto=".0f", labels={"duration_h":"Stunden","client":"Kunde"})
        fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    l2, r2 = st.columns(2)
    with l2:
        st.subheader("Top 10 Projekte")
        top = df.groupby("project")["duration_h"].sum().nlargest(10).sort_values().reset_index()
        fig = px.bar(top, x="duration_h", y="project", orientation="h",
                     color="duration_h", color_continuous_scale="Teal",
                     text_auto=".0f", labels={"duration_h":"Stunden","project":"Projekt"})
        fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with r2:
        st.subheader("Abrechenbar vs. Nicht-Abrechenbar")
        bd = df.groupby("is_billable")["duration_h"].sum().reset_index()
        bd["label"] = bd["is_billable"].map({True:"Abrechenbar",False:"Nicht-Abrechenbar"})
        fig = px.pie(bd, values="duration_h", names="label", hole=0.45,
                     color_discrete_sequence=["#2d6a9f","#e8b04b"])
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 2 – ENTWICKLUNG
# ════════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader(f"Stundenentwicklung ({gran})")
    ts = df.groupby(gc)["duration_h"].sum().reset_index().sort_values(gc)
    fig = px.line(ts, x=gc, y="duration_h", markers=True,
                  color_discrete_sequence=["#2d6a9f"],
                  labels={"duration_h":"Stunden", gc: gran})
    fig.update_traces(line_width=2.5, marker_size=7)
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    l, r = st.columns(2)
    with l:
        st.subheader("Abrechenbar im Verlauf")
        tb = df.groupby([gc,"is_billable"])["duration_h"].sum().reset_index().sort_values(gc)
        tb["Typ"] = tb["is_billable"].map({True:"Abrechenbar",False:"Nicht-Abrechenbar"})
        fig = px.area(tb, x=gc, y="duration_h", color="Typ",
                      color_discrete_sequence=["#2d6a9f","#e8b04b"],
                      labels={"duration_h":"Stunden", gc: gran})
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with r:
        st.subheader("% Abrechenbar – Effizienztrend")
        tp = (df.groupby(gc)
              .apply(lambda x: x["is_billable"].mean()*100, include_groups=False)
              .reset_index(name="pct").sort_values(gc))
        fig = px.line(tp, x=gc, y="pct", markers=True,
                      color_discrete_sequence=["#27ae60"],
                      labels={"pct":"% Abrechenbar", gc: gran})
        fig.add_hline(y=tp["pct"].mean(), line_dash="dash", line_color="gray",
                      annotation_text=f"Ø {tp['pct'].mean():.1f}%")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Neue Kunden pro Jahr")
    fy = df.groupby("client")["year"].min().reset_index().rename(columns={"year":"fy"})
    nc = fy.groupby("fy").size().reset_index(name="n")
    fig = px.bar(nc, x="fy", y="n", text_auto=True,
                 color_discrete_sequence=["#8e44ad"],
                 labels={"fy":"Jahr","n":"Neue Kunden"})
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 3 – TEAM
# ════════════════════════════════════════════════════════════
with tabs[2]:
    l, r = st.columns(2)
    with l:
        st.subheader("Stunden pro Person")
        bu = df.groupby("user")["duration_h"].sum().sort_values().reset_index()
        fig = px.bar(bu, x="duration_h", y="user", orientation="h",
                     color="duration_h", color_continuous_scale="Blues",
                     text_auto=".0f", labels={"duration_h":"Stunden","user":"Person"})
        fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)",
                          height=max(400, len(bu)*28))
        st.plotly_chart(fig, use_container_width=True)
    with r:
        st.subheader("% Abrechenbar pro Person")
        bp = (df.groupby("user")
              .apply(lambda x: x["is_billable"].mean()*100, include_groups=False)
              .reset_index(name="pct").sort_values("pct"))
        bp["color"] = bp["pct"].apply(lambda v: "#27ae60" if v>=60 else ("#e8b04b" if v>=30 else "#e74c3c"))
        fig = px.bar(bp, x="pct", y="user", orientation="h",
                     color="color", color_discrete_map="identity",
                     text_auto=".1f", labels={"pct":"% Abrechenbar","user":"Person"})
        fig.add_vline(x=60, line_dash="dash", line_color="gray", annotation_text="60% Ziel")
        fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                          height=max(400, len(bp)*28))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader(f"Top-10-Personen im Zeitverlauf ({gran})")
    top10u = df.groupby("user")["duration_h"].sum().nlargest(10).index.tolist()
    tu = (df[df["user"].isin(top10u)]
          .groupby([gc,"user"])["duration_h"].sum()
          .reset_index().sort_values(gc))
    fig = px.line(tu, x=gc, y="duration_h", color="user",
                  color_discrete_sequence=PAL,
                  labels={"duration_h":"Stunden", gc: gran, "user":"Person"})
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Heatmap: Stunden nach Wochentag & Person")
    wd_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    hm = (df.groupby(["user","weekday"])["duration_h"].sum()
          .reset_index()
          .pivot(index="user", columns="weekday", values="duration_h")
          .reindex(columns=[d for d in wd_order if d in df["weekday"].unique()])
          .fillna(0))
    fig = px.imshow(hm, color_continuous_scale="Blues", labels={"color":"Stunden"}, aspect="auto")
    fig.update_layout(height=max(400, len(hm)*30))
    st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 4 – KUNDEN
# ════════════════════════════════════════════════════════════
with tabs[3]:
    l, r = st.columns(2)
    with l:
        st.subheader("Top-12-Kunden im Zeitverlauf")
        top12c = df.groupby("client")["duration_h"].sum().nlargest(12).index.tolist()
        tc = (df[df["client"].isin(top12c)]
              .groupby([gc,"client"])["duration_h"].sum()
              .reset_index().sort_values(gc))
        fig = px.line(tc, x=gc, y="duration_h", color="client",
                      color_discrete_sequence=PAL,
                      labels={"duration_h":"Stunden", gc: gran, "client":"Kunde"})
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with r:
        st.subheader("Kundenlaufzeit vs. Gesamtstunden")
        cs = df.groupby("client").agg(
            total_h=("duration_h","sum"),
            first=("date","min"), last=("date","max")
        ).reset_index()
        cs["tage"] = (cs["last"]-cs["first"]).dt.days
        fig = px.scatter(cs, x="tage", y="total_h", text="client",
                         size="total_h", color="total_h",
                         color_continuous_scale="Blues", size_max=40,
                         labels={"tage":"Laufzeit (Tage)","total_h":"Gesamtstunden"})
        fig.update_traces(textposition="top center")
        fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Alle Kunden – Übersicht")
    ct = df.groupby("client").agg(
        Stunden=("duration_h","sum"), Buchungen=("duration_h","count"),
        Projekte=("project","nunique"), Personen=("user","nunique"),
        Erster=("date","min"), Letzter=("date","max")
    ).reset_index().sort_values("Stunden", ascending=False)
    ct["Stunden"] = ct["Stunden"].round(1)
    ct["Erster"]  = ct["Erster"].dt.strftime("%d.%m.%Y")
    ct["Letzter"] = ct["Letzter"].dt.strftime("%d.%m.%Y")
    st.dataframe(ct, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🔎 Einzelkunden-Analyse")
    sel_c = st.selectbox("Kunde wählen", sorted(df["client"].unique()))
    dfc = df[df["client"]==sel_c]
    cc1, cc2 = st.columns(2)
    with cc1:
        pm = dfc.groupby("project")["duration_h"].sum().reset_index()
        fig = px.pie(pm, values="duration_h", names="project",
                     color_discrete_sequence=PAL, hole=0.4,
                     title=f"Projektmix – {sel_c}")
        st.plotly_chart(fig, use_container_width=True)
    with cc2:
        mv = dfc.groupby("month")["duration_h"].sum().reset_index().sort_values("month")
        fig = px.bar(mv, x="month", y="duration_h",
                     color_discrete_sequence=["#2d6a9f"],
                     labels={"duration_h":"Stunden","month":"Monat"},
                     title=f"Monatsverlauf – {sel_c}")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 5 – PROJEKTE
# ════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader(f"Projektmix-Anteil im Zeitverlauf ({gran})")
    top15p = df.groupby("project")["duration_h"].sum().nlargest(15).index.tolist()
    tp = (df[df["project"].isin(top15p)]
          .groupby([gc,"project"])["duration_h"].sum()
          .reset_index().sort_values(gc))
    tot = tp.groupby(gc)["duration_h"].sum().rename("total")
    tp  = tp.join(tot, on=gc)
    tp["anteil"] = tp["duration_h"] / tp["total"] * 100
    fig = px.area(tp, x=gc, y="anteil", color="project",
                  color_discrete_sequence=PAL, groupnorm="",
                  labels={"anteil":"Anteil (%)", gc: gran, "project":"Projekt"})
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", height=500)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Alle Projekte – Übersicht")
    pt = df.groupby(["project","client"]).agg(
        Stunden=("duration_h","sum"), Buchungen=("duration_h","count"),
        Personen=("user","nunique"), Erster=("date","min"), Letzter=("date","max")
    ).reset_index().sort_values("Stunden", ascending=False)
    pt["Stunden"] = pt["Stunden"].round(1)
    pt["Erster"]  = pt["Erster"].dt.strftime("%d.%m.%Y")
    pt["Letzter"] = pt["Letzter"].dt.strftime("%d.%m.%Y")
    st.dataframe(pt, use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════
# TAB 6 – INTERN VS. EXTERN
# ════════════════════════════════════════════════════════════
with tabs[5]:
    st.subheader(f"Intern vs. Kunden-Zeit ({gran})")
    df["typ"] = df["is_internal"].map({True:"Intern",False:"Kunden"})
    ti = df.groupby([gc,"typ"])["duration_h"].sum().reset_index().sort_values(gc)
    fig = px.area(ti, x=gc, y="duration_h", color="typ",
                  color_discrete_sequence=["#e8b04b","#2d6a9f"],
                  labels={"duration_h":"Stunden", gc: gran, "typ":"Typ"})
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    l, r = st.columns(2)
    with l:
        st.subheader("% Interne Zeit pro Periode")
        pi = (df.groupby(gc)
              .apply(lambda x: x["is_internal"].mean()*100, include_groups=False)
              .reset_index(name="pct").sort_values(gc))
        fig = px.line(pi, x=gc, y="pct", markers=True,
                      color_discrete_sequence=["#e8b04b"],
                      labels={"pct":"% Intern", gc: gran})
        fig.add_hline(y=pi["pct"].mean(), line_dash="dash", line_color="gray",
                      annotation_text=f"Ø {pi['pct'].mean():.1f}%")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with r:
        st.subheader("Interner Projektmix")
        ip = (df[df["is_internal"]]
              .groupby("project")["duration_h"].sum()
              .nlargest(12).reset_index())
        if ip.empty:
            st.info("Keine internen Buchungen gefunden.")
        else:
            fig = px.pie(ip, values="duration_h", names="project",
                         color_discrete_sequence=PAL, hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 7 – FUN FACTS
# ════════════════════════════════════════════════════════════
with tabs[6]:
    st.subheader("🎉 Fun Facts & Kuriositäten")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("### 🌅 Frühaufsteher")
        if df["hour"].notna().any():
            early = df[df["hour"] < 7]
            if not early.empty:
                st.metric("Buchungen vor 7 Uhr", early.shape[0])
                st.metric("Top Person", early.groupby("user").size().idxmax())
            else:
                st.info("Keine vor 7 Uhr.")
        else:
            st.info("Keine Uhrzeitdaten.")

    with c2:
        st.markdown("### 🦉 Nachteulen")
        if df["hour"].notna().any():
            late = df[df["hour"] >= 21]
            if not late.empty:
                st.metric("Buchungen ab 21 Uhr", late.shape[0])
                st.metric("Top Person", late.groupby("user").size().idxmax())
            else:
                st.info("Keine ab 21 Uhr.")
        else:
            st.info("Keine Uhrzeitdaten.")

    with c3:
        st.markdown("### 🏋️ Wochenend-Warriors")
        we = df[df["weekday"].isin(["Saturday","Sunday"])]
        if not we.empty:
            st.metric("Wochenend-Stunden", f"{we['duration_h'].sum():.0f} h")
            st.metric("Champion", we.groupby("user")["duration_h"].sum().idxmax())
        else:
            st.info("Keine Wochenend-Buchungen.")

    st.markdown("---")
    c4, c5 = st.columns(2)
    with c4:
        st.markdown("### ⚡ Kürzeste & längste Buchung")
        pos = df[df["duration_h"] > 0]
        if not pos.empty:
            s = df.loc[pos["duration_h"].idxmin()]
            l_ = df.loc[df["duration_h"].idxmax()]
            st.info(f"**Kürzeste:** {s['duration_h']*60:.1f} min · {s['user']} · {s['project']}")
            st.success(f"**Längste:** {l_['duration_h']:.1f} h · {l_['user']} · {l_['project']}")

        st.markdown("### 🏆 Produktivster Tag")
        ds = df.groupby(df["date"].dt.date)["duration_h"].sum()
        if not ds.empty:
            st.success(f"**{ds.idxmax()}** mit {ds.max():.0f} h im Team")

    with c5:
        st.markdown("### 🕐 Buchungen nach Tageszeit")
        if df["hour"].notna().any():
            hd = df.groupby("hour").size().reset_index(name="Buchungen")
            fig = px.bar(hd, x="hour", y="Buchungen",
                         color="Buchungen", color_continuous_scale="Blues",
                         labels={"hour":"Uhrzeit"})
            fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("### 💬 Häufigste Wörter in Beschreibungen")
    stopwords = {
        "und","der","die","das","für","mit","an","auf","in","zu","von","bei",
        "ist","im","am","ein","eine","einer","einen","des","dem","den",
        "ich","wir","sie","es","er","hat","haben","the","and","for","with",
        "of","to","a","on","is","nan","","–","-"
    }
    txt   = " ".join(df["description"].astype(str)).lower()
    words = re.findall(r"\b[a-zäöüß]{3,}\b", txt)
    wf    = Counter(w for w in words if w not in stopwords)
    tw    = pd.DataFrame(wf.most_common(30), columns=["Wort","Häufigkeit"])
    fig   = px.bar(tw.sort_values("Häufigkeit"), x="Häufigkeit", y="Wort",
                   orientation="h", color="Häufigkeit",
                   color_continuous_scale="Blues", text_auto=True)
    fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)", height=600)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("⏱️ Clockify Insights · Streamlit & Plotly · Clockify CSV-Export")
