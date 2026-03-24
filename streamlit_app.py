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


# ── Hilfsfunktion: REVOIC-Kategorien ────────────────────────────────────────
def kategorisiere_revoic(row):
    proj  = str(row.get("project", "")).strip()
    desc  = str(row.get("description", "")).lower()

    # Projekt-basiert (Vorrang)
    if proj in ["ASK"]:                                        return "🎤 ASK / Amazon Sales Kongress"
    if proj in ["Seminare", "Seminar März/26"]:                return "🎓 Seminare"
    if proj in ["Meeting", "Weekly / Daily"]:                  return "🤝 Meetings & Abstimmung"
    if proj == "Weiterbildung":                                return "📚 Weiterbildung & Lernen"
    if proj in ["KI/Tool Entwicklung", "REVOIC.AI", "AXOLIST"]:return "🤖 KI & Tools"
    if proj == "Social Media":                                 return "📣 Social Media & Content"
    if proj == "Buchhaltung":                                  return "🧾 Buchhaltung & Admin"
    if proj == "HR (intern)":                                  return "👥 HR & Team"
    if proj in ["Business Development & Akquise", "Akquise"]: return "💼 Business Development"
    if proj == "Buch":                                         return "📖 Buch"
    if proj in ["Vorträge/Konferenz-Vorbereitungen",
                "Marketing / Roundtable"]:                     return "🎤 ASK / Amazon Sales Kongress"
    if proj == "Organisation":                                 return "🗂️ Organisation & Planung"
    if proj == "Büromanagement":                               return "🗂️ Organisation & Planung"
    if proj in ["Website"]:                                    return "🌐 Website & IT"

    # Beschreibungs-basiert als Fallback
    if any(k in desc for k in ["meeting","meet","besprechung","jour fixe","sync","call","standup","daily","weekly","all hands"]):
        return "🤝 Meetings & Abstimmung"
    if any(k in desc for k in ["seminar","ask ","ask-","kongress","vortrag","konferenz"]):
        return "🎤 ASK / Amazon Sales Kongress"
    if any(k in desc for k in ["weiterbildung","learning","lernen","kurs","training","schulung","webinar"]):
        return "📚 Weiterbildung & Lernen"
    if any(k in desc for k in ["social media","linkedin","instagram","content","post","newsletter","podcast","youtube"]):
        return "📣 Social Media & Content"
    if any(k in desc for k in ["akquise","business development","lead","close","pitch","angebot"]):
        return "💼 Business Development"
    if any(k in desc for k in ["buchhaltung","rechnung","invoice","steuer","abrechnung","zahlung"]):
        return "🧾 Buchhaltung & Admin"
    if any(k in desc for k in ["hr","personal","mitarbeiter","onboarding","bewerbung","urlaub","krank","vertrag"]):
        return "👥 HR & Team"
    if any(k in desc for k in ["ki ","ki/","tool","ai ","gpt","claude","automation","revoic.ai","axolist"]):
        return "🤖 KI & Tools"
    if any(k in desc for k in ["website","web","it ","server","domain","hosting","tech","bria"]):
        return "🌐 Website & IT"
    if any(k in desc for k in ["clickup","asana","einsatz","aufgaben","task","inbox","mattermost","checkout","planung","organisation"]):
        return "🗂️ Organisation & Planung"

    return "📌 Sonstiges Intern"


@st.cache_data
def load_data(f) -> pd.DataFrame:
    try:
        df = pd.read_csv(f, low_memory=False)
    except Exception as e:
        st.error(f"CSV konnte nicht geladen werden: {e}")
        st.stop()

    df.columns = df.columns.str.strip()

    rename = {
        "Benutzer": "user", "User": "user", "Nutzer": "user",
        "Kunde": "client", "Client": "client",
        "Projekt": "project", "Project": "project",
        "Beschreibung": "description", "Description": "description",
        "Abrechenbar": "billable", "Billable": "billable",
        "Startdatum": "start_date", "Start Date": "start_date", "Datum": "start_date",
        "Startzeit": "start_time", "Start Time": "start_time",
        "Dauer (dezimal)":    "duration_h",
        "Dauer (Dezimalzahl)":"duration_h",
        "Duration (decimal)": "duration_h",
        "Dauer (decimal)":    "duration_h",
    }
    df.rename(columns={k: v for k, v in rename.items() if k in df.columns}, inplace=True)

    if "duration_h" not in df.columns:
        for c in df.columns:
            if ("dezimal" in c.lower() or "decimal" in c.lower()):
                df.rename(columns={c: "duration_h"}, inplace=True)
                break

    if "duration_h" not in df.columns:
        for c in df.columns:
            if "dauer" in c.lower() or "duration" in c.lower():
                parsed = df[c].astype(str).str.extract(r"(\d+):(\d+)")
                if parsed.notna().any().any():
                    df["duration_h"] = (
                        pd.to_numeric(parsed[0], errors="coerce").fillna(0) +
                        pd.to_numeric(parsed[1], errors="coerce").fillna(0) / 60
                    )
                break

    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    if "duration_h" in df.columns:
        col = df["duration_h"]
        if pd.api.types.is_numeric_dtype(col):
            df["duration_h"] = col.fillna(0.0)
        else:
            df["duration_h"] = pd.to_numeric(
                col.astype(str).str.strip().str.replace(",", ".", regex=False),
                errors="coerce"
            ).fillna(0.0)
    else:
        df["duration_h"] = 0.0

    df["date"]    = pd.to_datetime(df.get("start_date", pd.Series(dtype=str)), dayfirst=True, errors="coerce")
    df["year"]    = df["date"].dt.year
    df["month"]   = df["date"].dt.to_period("M").astype(str)
    df["quarter"] = df["date"].dt.to_period("Q").astype(str)
    df["weekday"] = df["date"].dt.day_name()

    if "start_time" in df.columns:
        t = df["start_time"].astype(str)
        df["hour"] = pd.to_datetime(t, format="%H:%M", errors="coerce").dt.hour
        mask = df["hour"].isna()
        df.loc[mask, "hour"] = pd.to_datetime(t[mask], format="%H:%M:%S", errors="coerce").dt.hour
    else:
        df["hour"] = df["date"].dt.hour

    if "billable" in df.columns:
        df["is_billable"] = df["billable"].astype(str).str.strip().str.lower().isin(["ja","yes","true","1","wahr"])
    else:
        df["is_billable"] = False

    df["client"] = (df["client"].fillna("Kein Kunde").astype(str).str.strip()
                    if "client" in df.columns else "Unbekannt")
    df["is_internal"] = df["client"].str.lower().str.contains(
        "revoic|intern|internal|eigene|administration", na=False)
    df["project"]     = (df["project"].fillna("Kein Projekt").astype(str).str.strip()
                         if "project" in df.columns else "Unbekannt")
    df["user"]        = (df["user"].fillna("Unbekannt").astype(str).str.strip()
                         if "user" in df.columns else "Unbekannt")
    df["description"] = (df["description"].fillna("").astype(str)
                         if "description" in df.columns else "")
    df["is_alt"]      = df["project"].str.lower().str.startswith("(alt)")

    # REVOIC-Kategorie
    df["revoic_kat"] = df.apply(
        lambda r: kategorisiere_revoic(r) if str(r.get("client","")).upper() == "REVOIC" else "", axis=1
    )

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

if df_raw["duration_h"].sum() == 0:
    st.warning("⚠️ Alle Stunden = 0. Verfügbare Spalten: " + ", ".join(df_raw.columns.tolist()))

st.sidebar.markdown("### 🔍 Filter")
years       = sorted(df_raw["year"].dropna().unique().astype(int).tolist())
sel_years   = st.sidebar.multiselect("Jahr(e)", years, default=years)
sel_users   = st.sidebar.multiselect("Mitarbeiter:in", sorted(df_raw["user"].unique()), default=sorted(df_raw["user"].unique()))

# Nur externe Kunden im Filter (REVOIC hat eigenen Tab)
ext_clients = sorted(df_raw[~df_raw["is_internal"]]["client"].unique().tolist())
sel_clients = st.sidebar.multiselect("Kunde (extern)", ext_clients, default=ext_clients)

hide_alt    = st.sidebar.checkbox("ALT-Projekte ausblenden", value=False)
gran        = st.sidebar.radio("Zeitgranularität", ["Monat", "Quartal", "Jahr"], index=0)
gc          = {"Monat": "month", "Quartal": "quarter", "Jahr": "year"}[gran]
st.sidebar.markdown("---")
st.sidebar.caption(f"📊 {len(df_raw):,} Einträge geladen")

# Externe df (für die meisten Tabs)
df_ext = df_raw[
    df_raw["year"].isin(sel_years) &
    df_raw["user"].isin(sel_users) &
    (~df_raw["is_internal"]) &
    df_raw["client"].isin(sel_clients)
].copy()

# Internes df (REVOIC)
df_int = df_raw[
    df_raw["year"].isin(sel_years) &
    df_raw["user"].isin(sel_users) &
    df_raw["is_internal"]
].copy()

if hide_alt:
    df_ext = df_ext[~df_ext["is_alt"]]
    df_int = df_int[~df_int["is_alt"]]

df = df_ext  # default für externe Tabs

PAL = px.colors.qualitative.Bold

# ── HEADER ───────────────────────────────────────────────────────────────────
st.markdown("# ⏱️ Clockify Insights")
d_min = df_raw["date"].min()
d_max = df_raw["date"].max()
ext_bill_h = df_ext[df_ext["is_billable"]]["duration_h"].sum()
st.markdown(
    f"**{len(df_raw):,} Einträge gesamt** · "
    f"{df_raw['user'].nunique()} Personen · "
    f"{df_raw['date'].min().strftime('%d.%m.%Y') if pd.notna(d_min) else '?'} – "
    f"{df_raw['date'].max().strftime('%d.%m.%Y') if pd.notna(d_max) else '?'} · "
    f"💰 **{ext_bill_h:,.0f} h extern & abrechenbar**"
)
st.markdown("---")

tabs = st.tabs([
    "📊 Überblick",
    "📈 Entwicklung",
    "👥 Team",
    "🏢 Kunden",
    "🗂️ Projekte",
    "🔄 Intern vs. Extern",
    "🏠 REVOIC Intern",
    "🎉 Fun Facts",
])

# ════════════════════════════════════════════════════════════
# TAB 1 – ÜBERBLICK (nur externe)
# ════════════════════════════════════════════════════════════
with tabs[0]:
    st.caption("📌 Dieser Tab zeigt nur **externe Kunden** (REVOIC intern → Tab 'REVOIC Intern')")
    c1,c2,c3,c4,c5 = st.columns(5)
    for col, lbl, val, sub in zip(
        [c1,c2,c3,c4,c5],
        ["⏱️ Externe Stunden","💰 Abrechenbar (extern)","✅ % Abrechenbar","🏢 Kunden","📋 Buchungen"],
        [f"{df_ext['duration_h'].sum():,.0f} h",
         f"{df_ext[df_ext['is_billable']]['duration_h'].sum():,.0f} h",
         f"{df_ext['is_billable'].mean()*100:.1f} %",
         str(df_ext['client'].nunique()),
         f"{len(df_ext):,}"],
        ["Externe Kunden gesamt","Extern & abrechenbar","Anteil abrechenbar","Einzigartige Kunden","Einträge"]
    ):
        col.markdown(f'<div class="metric-card"><h3>{lbl}</h3><h1>{val}</h1><p>{sub}</p></div>',
                     unsafe_allow_html=True)

    st.markdown("---")
    l, r = st.columns(2)
    with l:
        st.subheader("Externe Stunden pro Jahr")
        by_year = df_ext.groupby("year")["duration_h"].sum().reset_index()
        fig = px.bar(by_year, x="year", y="duration_h", color="year",
                     color_discrete_sequence=PAL, text_auto=".0f",
                     labels={"duration_h":"Stunden","year":"Jahr"})
        fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with r:
        st.subheader("Top 10 externe Kunden")
        top = df_ext.groupby("client")["duration_h"].sum().nlargest(10).sort_values().reset_index()
        fig = px.bar(top, x="duration_h", y="client", orientation="h",
                     color="duration_h", color_continuous_scale="Blues",
                     text_auto=".0f", labels={"duration_h":"Stunden","client":"Kunde"})
        fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    l2, r2 = st.columns(2)
    with l2:
        st.subheader("Top 10 externe Projekte")
        top = df_ext.groupby("project")["duration_h"].sum().nlargest(10).sort_values().reset_index()
        fig = px.bar(top, x="duration_h", y="project", orientation="h",
                     color="duration_h", color_continuous_scale="Teal",
                     text_auto=".0f", labels={"duration_h":"Stunden","project":"Projekt"})
        fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with r2:
        st.subheader("Abrechenbar vs. Nicht-Abrechenbar (extern)")
        bd = df_ext.groupby("is_billable")["duration_h"].sum().reset_index()
        bd["label"] = bd["is_billable"].map({True:"Abrechenbar",False:"Nicht-Abrechenbar"})
        fig = px.pie(bd, values="duration_h", names="label", hole=0.45,
                     color_discrete_sequence=["#2d6a9f","#e8b04b"])
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 2 – ENTWICKLUNG
# ════════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader(f"Externe Stundenentwicklung ({gran})")
    ts = df_ext.groupby(gc)["duration_h"].sum().reset_index().sort_values(gc)
    fig = px.area(ts, x=gc, y="duration_h", markers=True, color_discrete_sequence=["#2d6a9f"],
                  labels={"duration_h":"Stunden", gc: gran})
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    l, r = st.columns(2)
    with l:
        st.subheader("Abrechenbar im Verlauf (extern)")
        tb = df_ext.groupby([gc,"is_billable"])["duration_h"].sum().reset_index().sort_values(gc)
        tb["Typ"] = tb["is_billable"].map({True:"Abrechenbar",False:"Nicht-Abrechenbar"})
        fig = px.bar(tb, x=gc, y="duration_h", color="Typ", barmode="stack",
                     color_discrete_sequence=["#2d6a9f","#e8b04b"],
                     labels={"duration_h":"Stunden", gc: gran})
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with r:
        st.subheader("% Abrechenbar – Effizienztrend (extern)")
        tp = (df_ext.groupby(gc)
              .apply(lambda x: x["is_billable"].mean()*100, include_groups=False)
              .reset_index(name="pct").sort_values(gc))
        fig = px.line(tp, x=gc, y="pct", markers=True, color_discrete_sequence=["#27ae60"],
                      labels={"pct":"% Abrechenbar", gc: gran})
        fig.add_hline(y=tp["pct"].mean(), line_dash="dash", line_color="gray",
                      annotation_text=f"Ø {tp['pct'].mean():.1f}%")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Neue externe Kunden pro Jahr")
    fy = df_ext.groupby("client")["year"].min().reset_index().rename(columns={"year":"fy"})
    nc = fy.groupby("fy").size().reset_index(name="n")
    fig = px.bar(nc, x="fy", y="n", text_auto=True, color_discrete_sequence=["#8e44ad"],
                 labels={"fy":"Jahr","n":"Neue Kunden"})
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 3 – TEAM (alle inkl. intern)
# ════════════════════════════════════════════════════════════
with tabs[2]:
    df_all_users = df_raw[df_raw["year"].isin(sel_years) & df_raw["user"].isin(sel_users)].copy()

    l, r = st.columns(2)
    with l:
        st.subheader("Gesamtstunden pro Person (inkl. intern)")
        bu = df_all_users.groupby("user")["duration_h"].sum().sort_values().reset_index()
        fig = px.bar(bu, x="duration_h", y="user", orientation="h",
                     color="duration_h", color_continuous_scale="Blues",
                     text_auto=".0f", labels={"duration_h":"Stunden","user":"Person"})
        fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)",
                          height=max(400, len(bu)*28))
        st.plotly_chart(fig, use_container_width=True)
    with r:
        st.subheader("% Abrechenbar (extern) pro Person")
        bp = (df_ext.groupby("user")
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
    st.subheader(f"Top-10-Personen im Zeitverlauf – extern ({gran})")
    top10u = df_ext.groupby("user")["duration_h"].sum().nlargest(10).index.tolist()
    tu = df_ext[df_ext["user"].isin(top10u)].groupby([gc,"user"])["duration_h"].sum().reset_index().sort_values(gc)
    fig = px.line(tu, x=gc, y="duration_h", color="user", color_discrete_sequence=PAL,
                  labels={"duration_h":"Stunden", gc: gran, "user":"Person"})
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Heatmap: Stunden nach Wochentag & Person")
    wd_order  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    wd_labels = {"Monday":"Mo","Tuesday":"Di","Wednesday":"Mi","Thursday":"Do","Friday":"Fr","Saturday":"Sa","Sunday":"So"}
    hm = (df_all_users.groupby(["user","weekday"])["duration_h"].sum()
          .reset_index().pivot(index="user", columns="weekday", values="duration_h")
          .reindex(columns=[d for d in wd_order if d in df_all_users["weekday"].unique()]).fillna(0))
    hm.columns = [wd_labels.get(c,c) for c in hm.columns]
    fig = px.imshow(hm, color_continuous_scale="Blues", labels={"color":"Stunden"}, aspect="auto")
    fig.update_layout(height=max(400, len(hm)*30))
    st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 4 – KUNDEN (nur extern)
# ════════════════════════════════════════════════════════════
with tabs[3]:
    l, r = st.columns(2)
    with l:
        st.subheader("Top-12-Kunden im Zeitverlauf (extern)")
        top12c = df_ext.groupby("client")["duration_h"].sum().nlargest(12).index.tolist()
        tc = df_ext[df_ext["client"].isin(top12c)].groupby([gc,"client"])["duration_h"].sum().reset_index().sort_values(gc)
        fig = px.line(tc, x=gc, y="duration_h", color="client", color_discrete_sequence=PAL,
                      labels={"duration_h":"Stunden", gc: gran, "client":"Kunde"})
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with r:
        st.subheader("Kundenlaufzeit vs. Gesamtstunden (extern)")
        cs = df_ext.groupby("client").agg(
            total_h=("duration_h","sum"), first=("date","min"), last=("date","max")
        ).reset_index()
        cs["tage"] = (cs["last"]-cs["first"]).dt.days
        cs = cs[cs["total_h"] > 0]
        fig = px.scatter(cs, x="tage", y="total_h", text="client",
                         size="total_h", color="total_h", color_continuous_scale="Blues", size_max=50,
                         labels={"tage":"Laufzeit (Tage)","total_h":"Gesamtstunden"},
                         hover_data={"client":True,"total_h":":.1f","tage":True})
        fig.update_traces(textposition="top center", textfont_size=9)
        fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Alle externen Kunden – Übersicht")
    ct = df_ext.groupby("client").agg(
        Stunden=("duration_h","sum"), Buchungen=("duration_h","count"),
        Projekte=("project","nunique"), Personen=("user","nunique"),
        Erster=("date","min"), Letzter=("date","max")
    ).reset_index().sort_values("Stunden", ascending=False)
    bill_h = df_ext[df_ext["is_billable"]].groupby("client")["duration_h"].sum().rename("Abrechenbar_h")
    ct = ct.join(bill_h, on="client")
    ct["Abrechenbar_h"] = ct["Abrechenbar_h"].fillna(0).round(1)
    ct["% Abrechenbar"] = (ct["Abrechenbar_h"] / ct["Stunden"].replace(0,1)*100).round(1).astype(str) + "%"
    ct["Stunden"] = ct["Stunden"].round(1)
    ct["Erster"]  = ct["Erster"].dt.strftime("%d.%m.%Y")
    ct["Letzter"] = ct["Letzter"].dt.strftime("%d.%m.%Y")
    st.dataframe(ct[["client","Stunden","Abrechenbar_h","% Abrechenbar","Buchungen","Projekte","Personen","Erster","Letzter"]],
                 use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🔎 Einzelkunden-Analyse")
    sel_c = st.selectbox("Kunde wählen", sorted(df_ext["client"].unique()))
    dfc = df_ext[df_ext["client"]==sel_c]
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Gesamt-Stunden", f"{dfc['duration_h'].sum():.1f} h")
    m2.metric("Abrechenbar", f"{dfc[dfc['is_billable']]['duration_h'].sum():.1f} h")
    m3.metric("Buchungen", f"{len(dfc):,}")
    m4.metric("Aktive Monate", dfc["month"].nunique())
    cc1, cc2 = st.columns(2)
    with cc1:
        pm = dfc.groupby("project")["duration_h"].sum().reset_index()
        fig = px.pie(pm, values="duration_h", names="project",
                     color_discrete_sequence=PAL, hole=0.4, title=f"Projektmix – {sel_c}")
        st.plotly_chart(fig, use_container_width=True)
    with cc2:
        mv = dfc.groupby("month")["duration_h"].sum().reset_index().sort_values("month")
        fig = px.bar(mv, x="month", y="duration_h", color_discrete_sequence=["#2d6a9f"],
                     labels={"duration_h":"Stunden","month":"Monat"}, title=f"Monatsverlauf – {sel_c}")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 5 – PROJEKTE (extern, mit abrechenbar/nicht)
# ════════════════════════════════════════════════════════════
with tabs[4]:
    n_alt = df_ext["is_alt"].sum()
    if n_alt > 0:
        st.info(f"ℹ️ **ALT-Projekte:** {n_alt:,} Buchungen · {df_ext[df_ext['is_alt']]['duration_h'].sum():.0f} h. Über Sidebar ausblendbar.")

    st.subheader(f"Externe Projekte: Abrechenbar vs. Nicht-Abrechenbar im Zeitverlauf ({gran})")
    top12p = df_ext.groupby("project")["duration_h"].sum().nlargest(12).index.tolist()
    tp_bill = (df_ext[df_ext["project"].isin(top12p)]
               .groupby([gc,"project","is_billable"])["duration_h"].sum().reset_index().sort_values(gc))
    tp_bill["Typ"] = tp_bill["is_billable"].map({True:"Abrechenbar",False:"Nicht-Abrechenbar"})
    tp_bill["Projekt_Typ"] = tp_bill["project"] + " (" + tp_bill["Typ"] + ")"
    fig = px.bar(tp_bill, x=gc, y="duration_h", color="project", pattern_shape="Typ",
                 pattern_shape_map={"Abrechenbar":"","Nicht-Abrechenbar":"/"},
                 barmode="stack", color_discrete_sequence=PAL,
                 labels={"duration_h":"Stunden", gc: gran})
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", height=500)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Alle externen Projekte – Übersicht")
    pt = df_ext.groupby(["project","client"]).agg(
        Stunden=("duration_h","sum"), Buchungen=("duration_h","count"),
        Personen=("user","nunique"), Erster=("date","min"), Letzter=("date","max")
    ).reset_index().sort_values("Stunden", ascending=False)
    bill_p = df_ext[df_ext["is_billable"]].groupby(["project","client"])["duration_h"].sum().rename("Abrechenbar_h")
    pt = pt.join(bill_p, on=["project","client"])
    pt["Abrechenbar_h"] = pt["Abrechenbar_h"].fillna(0).round(1)
    pt["% Abr."] = (pt["Abrechenbar_h"]/pt["Stunden"].replace(0,1)*100).round(0).astype(int).astype(str)+"%"
    pt["Stunden"] = pt["Stunden"].round(1)
    pt["ALT"] = pt["project"].str.lower().str.startswith("(alt)").map({True:"⚠️",False:""})
    pt["Erster"] = pt["Erster"].dt.strftime("%d.%m.%Y")
    pt["Letzter"] = pt["Letzter"].dt.strftime("%d.%m.%Y")
    st.dataframe(pt[["ALT","project","client","Stunden","Abrechenbar_h","% Abr.","Buchungen","Personen","Erster","Letzter"]],
                 use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════
# TAB 6 – INTERN VS. EXTERN
# ════════════════════════════════════════════════════════════
with tabs[5]:
    df_ie = df_raw[df_raw["year"].isin(sel_years) & df_raw["user"].isin(sel_users)].copy()
    df_ie["typ"] = df_ie["is_internal"].map({True:"🏠 Intern (REVOIC)","False":"🏢 Extern"})
    df_ie["typ"] = df_ie["is_internal"].map({True:"🏠 Intern (REVOIC)",False:"🏢 Extern"})

    st.subheader(f"Intern vs. Extern ({gran})")
    ti = df_ie.groupby([gc,"typ"])["duration_h"].sum().reset_index().sort_values(gc)
    fig = px.bar(ti, x=gc, y="duration_h", color="typ", barmode="stack",
                 color_discrete_sequence=["#e8b04b","#2d6a9f"],
                 labels={"duration_h":"Stunden", gc: gran, "typ":"Typ"})
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    l, r = st.columns(2)
    with l:
        st.subheader("% Interne Zeit pro Periode")
        pi = (df_ie.groupby(gc).apply(lambda x: x["is_internal"].mean()*100, include_groups=False)
              .reset_index(name="pct").sort_values(gc))
        fig = px.line(pi, x=gc, y="pct", markers=True, color_discrete_sequence=["#e8b04b"],
                      labels={"pct":"% Intern", gc: gran})
        fig.add_hline(y=pi["pct"].mean(), line_dash="dash", line_color="gray",
                      annotation_text=f"Ø {pi['pct'].mean():.1f}%")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with r:
        st.subheader("Interner Projektmix")
        ip = df_int.groupby("project")["duration_h"].sum().nlargest(12).reset_index()
        if ip.empty:
            st.info("Keine internen Buchungen.")
        else:
            fig = px.pie(ip, values="duration_h", names="project",
                         color_discrete_sequence=PAL, hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 7 – REVOIC INTERN
# ════════════════════════════════════════════════════════════
with tabs[6]:
    st.markdown("## 🏠 REVOIC – Interne Aufgaben")
    st.caption("Alle Buchungen auf den Kunden REVOIC, kategorisiert nach Tätigkeitsbereich.")

    total_int  = df_int["duration_h"].sum()
    bill_int   = df_int[df_int["is_billable"]]["duration_h"].sum()
    ask_sem_h  = df_int[df_int["revoic_kat"].isin(["🎤 ASK / Amazon Sales Kongress","🎓 Seminare"])]["duration_h"].sum()

    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Interne Stunden gesamt", f"{total_int:,.0f} h")
    m2.metric("Davon abrechenbar (Seminare/ASK)", f"{bill_int:,.0f} h")
    m3.metric("Seminare & ASK gesamt", f"{ask_sem_h:,.0f} h")
    m4.metric("Interne Buchungen", f"{len(df_int):,}")

    st.markdown("---")
    st.subheader("Interne Zeit nach Kategorie")
    kat_sum = df_int.groupby("revoic_kat")["duration_h"].sum().sort_values(ascending=True).reset_index()
    fig = px.bar(kat_sum, x="duration_h", y="revoic_kat", orientation="h",
                 color="duration_h", color_continuous_scale="Blues",
                 text_auto=".0f", labels={"duration_h":"Stunden","revoic_kat":"Bereich"})
    fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)", height=500)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader(f"Interne Kategorien im Zeitverlauf ({gran})")
    kat_ts = df_int.groupby([gc,"revoic_kat"])["duration_h"].sum().reset_index().sort_values(gc)
    fig = px.bar(kat_ts, x=gc, y="duration_h", color="revoic_kat", barmode="stack",
                 color_discrete_sequence=PAL,
                 labels={"duration_h":"Stunden", gc: gran, "revoic_kat":"Bereich"})
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", height=450)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("🎓 Seminare & ASK – Details")
        ask_sem = df_int[df_int["revoic_kat"].isin(["🎤 ASK / Amazon Sales Kongress","🎓 Seminare"])].copy()
        if not ask_sem.empty:
            as_sum = ask_sem.groupby(["project","is_billable"])["duration_h"].sum().reset_index()
            as_sum["Typ"] = as_sum["is_billable"].map({True:"Abrechenbar 💰",False:"Nicht abrechenbar"})
            fig = px.bar(as_sum, x="duration_h", y="project", color="Typ", orientation="h",
                         barmode="stack",
                         color_discrete_sequence=["#27ae60","#e8b04b"],
                         labels={"duration_h":"Stunden","project":"Projekt"},
                         text_auto=".0f")
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

            st.markdown(f"**ASK:** {df_int[df_int['revoic_kat']=='🎤 ASK / Amazon Sales Kongress']['duration_h'].sum():.0f} h gesamt")
            st.markdown(f"**Seminare:** {df_int[df_int['revoic_kat']=='🎓 Seminare']['duration_h'].sum():.0f} h gesamt")

    with col_b:
        st.subheader("🤝 Meeting-Analyse")
        meetings = df_int[df_int["revoic_kat"] == "🤝 Meetings & Abstimmung"].copy()
        if not meetings.empty:
            # Meeting-Typen aus Beschreibungen clustern
            def meeting_typ(desc):
                d = str(desc).lower()
                if "weekly" in d: return "Weekly"
                if "daily" in d:  return "Daily"
                if "all hands" in d or "allhands" in d: return "All Hands"
                if "jour" in d or "jf " in d: return "Jour Fixe"
                if "kick" in d:   return "Kickoff"
                if "retro" in d:  return "Retro"
                return "Sonstiges Meeting"
            meetings["meeting_typ"] = meetings["description"].apply(meeting_typ)
            mt = meetings.groupby("meeting_typ")["duration_h"].sum().sort_values(ascending=True).reset_index()
            fig = px.bar(mt, x="duration_h", y="meeting_typ", orientation="h",
                         color="duration_h", color_continuous_scale="Purples",
                         text_auto=".0f", labels={"duration_h":"Stunden","meeting_typ":"Meeting-Typ"})
            fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Abrechenbare vs. Nicht-abrechenbare interne Zeit")
    int_bill = df_int.groupby(["revoic_kat","is_billable"])["duration_h"].sum().reset_index()
    int_bill["Typ"] = int_bill["is_billable"].map({True:"Abrechenbar 💰",False:"Nicht abrechenbar"})
    fig = px.bar(int_bill, x="duration_h", y="revoic_kat", color="Typ", orientation="h",
                 barmode="stack",
                 color_discrete_sequence=["#27ae60","#bdc3c7"],
                 labels={"duration_h":"Stunden","revoic_kat":"Bereich"},
                 text_auto=".0f")
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", height=500)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Detailansicht: Interne Kategorie wählen")
    sel_kat = st.selectbox("Bereich", sorted(df_int["revoic_kat"].unique()))
    dk = df_int[df_int["revoic_kat"] == sel_kat]
    k1,k2,k3 = st.columns(3)
    k1.metric("Stunden", f"{dk['duration_h'].sum():.1f} h")
    k2.metric("Buchungen", f"{len(dk):,}")
    k3.metric("Personen beteiligt", dk["user"].nunique())

    top_desc = dk.groupby("description")["duration_h"].sum().nlargest(15).sort_values().reset_index()
    fig = px.bar(top_desc, x="duration_h", y="description", orientation="h",
                 color="duration_h", color_continuous_scale="Blues",
                 text_auto=".1f", labels={"duration_h":"Stunden","description":"Beschreibung"})
    fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)", height=450)
    st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 8 – FUN FACTS
# ════════════════════════════════════════════════════════════
with tabs[7]:
    df_all = df_raw[df_raw["year"].isin(sel_years) & df_raw["user"].isin(sel_users)].copy()
    st.subheader("🎉 Fun Facts & Kuriositäten")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### 🌅 Frühaufsteher")
        if df_all["hour"].notna().any():
            early = df_all[df_all["hour"] < 7]
            if not early.empty:
                top_e = early.groupby("user")["duration_h"].agg(["sum","count"])
                nm = top_e["count"].idxmax()
                st.metric("Buchungen vor 7 Uhr", f"{early.shape[0]:,}")
                st.metric("Stunden vor 7 Uhr", f"{early['duration_h'].sum():.1f} h")
                st.metric("Top Person", nm)
                st.caption(f"{top_e.loc[nm,'count']:.0f} Buchungen · {top_e.loc[nm,'sum']:.1f} h")
    with c2:
        st.markdown("### 🦉 Nachteulen")
        if df_all["hour"].notna().any():
            late = df_all[df_all["hour"] >= 21]
            if not late.empty:
                top_l = late.groupby("user")["duration_h"].agg(["sum","count"])
                nm = top_l["count"].idxmax()
                st.metric("Buchungen ab 21 Uhr", f"{late.shape[0]:,}")
                st.metric("Stunden ab 21 Uhr", f"{late['duration_h'].sum():.1f} h")
                st.metric("Top Person", nm)
                st.caption(f"{top_l.loc[nm,'count']:.0f} Buchungen · {top_l.loc[nm,'sum']:.1f} h")
    with c3:
        st.markdown("### 🏋️ Wochenend-Warriors")
        we = df_all[df_all["weekday"].isin(["Saturday","Sunday"])]
        if not we.empty:
            top_w = we.groupby("user")["duration_h"].agg(["sum","count"])
            nm = top_w["sum"].idxmax()
            st.metric("Wochenend-Stunden", f"{we['duration_h'].sum():.0f} h")
            st.metric("Buchungen", f"{len(we):,}")
            st.metric("Champion", nm)
            st.caption(f"{top_w.loc[nm,'count']:.0f} Buchungen · {top_w.loc[nm,'sum']:.1f} h")

    st.markdown("---")
    c4, c5 = st.columns(2)
    with c4:
        st.markdown("### ⚡ Kürzeste & längste Buchung")
        pos = df_all[df_all["duration_h"] > 0]
        if not pos.empty:
            s = df_all.loc[pos["duration_h"].idxmin()]
            l_ = df_all.loc[df_all["duration_h"].idxmax()]
            st.info(f"**Kürzeste:** {s['duration_h']*60:.1f} min · {s['user']} · {s['project']}\n\n📝 \"{str(s['description'])[:60]}\"")
            st.success(f"**Längste:** {l_['duration_h']:.1f} h · {l_['user']} · {l_['project']}\n\n📝 \"{str(l_['description'])[:60]}\"")
        st.markdown("### 🏆 Produktivster Tag")
        ds = df_all.groupby(df_all["date"].dt.date)["duration_h"].sum()
        if not ds.empty:
            bd = ds.idxmax()
            st.success(f"**{bd}** · {ds.max():.0f} h · {df_all[df_all['date'].dt.date==bd]['user'].nunique()} Personen aktiv")
        st.markdown("### 📋 Meiste Buchungen an einem Tag")
        dc = df_all.groupby([df_all["date"].dt.date,"user"]).size()
        if not dc.empty:
            idx = dc.idxmax()
            st.info(f"**{idx[1]}** · {dc.max()} Buchungen am {idx[0]}")
    with c5:
        st.markdown("### 🕐 Buchungen nach Tageszeit")
        if df_all["hour"].notna().any():
            hd = df_all.groupby("hour").agg(Buchungen=("duration_h","count"), Stunden=("duration_h","sum")).reset_index()
            fig = px.bar(hd, x="hour", y="Buchungen", color="Stunden", color_continuous_scale="Blues",
                         labels={"hour":"Uhrzeit"})
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("### 🥚 Easter Eggs aus euren Buchungen")
    e1, e2, e3 = st.columns(3)
    with e1:
        st.markdown("#### 🕵️ Maiks Geheimnisse")
        ms = df_all[df_all["description"].str.contains("darfst alles", case=False, na=False)]
        if not ms.empty:
            st.info(f"**\"du darfst alles Essen, aber nicht alles wissen\"**\n\n🔒 {ms['duration_h'].sum():.1f} h C-Level-Geheimnisse")
        st.markdown("#### 😤 Ehrlichste Buchung")
        eh = df_all[df_all["description"].str.contains("weil ich doof", case=False, na=False)]
        if not eh.empty:
            r = eh.iloc[0]
            st.warning(f"**\"{r['description'][:90]}\"**\n\n🏅 {r['user']} · {r['duration_h']*60:.0f} Min")
    with e2:
        st.markdown("#### 🌙 Marathon-Buchungen (>20h)")
        marathon = df_all[df_all["duration_h"] > 20].sort_values("duration_h", ascending=False)
        for _, r in marathon.head(3).iterrows():
            st.error(f"**{r['duration_h']:.0f} h** – {r['user']}\n\n📝 \"{str(r['description'])[:50]}\"")
        st.markdown("#### 🧹 Büropflichten getrackt")
        buero = df_all[df_all["description"].str.contains("kaffeesatz|sitzball|küchenbar", case=False, na=False)]
        if not buero.empty:
            r = buero.iloc[0]
            st.info(f"**\"{r['description'][:80]}\"**\n\n🧹 {r['user']} · {r['duration_h']*60:.0f} Min")
    with e3:
        st.markdown("#### 😱 Chaos-Meter")
        chaos = df_all[df_all["description"].str.contains("chaos", case=False, na=False)]
        if not chaos.empty:
            top_c = chaos.groupby("user").size().sort_values(ascending=False)
            st.warning(f"**{len(chaos)}x** \"Chaos\" in Buchungen\n\n" +
                       "\n".join([f"- {u}: {n}x" for u,n in top_c.head(5).items()]))
        st.markdown("#### 👻 Phantom-Projekte")
        pc = df_all.groupby("project").size()
        einmal = pc[pc==1].index.tolist()
        if einmal:
            st.info(f"**{len(einmal)} Projekte** mit genau 1 Buchung:\n\n" + ", ".join(einmal[:6]))

    st.markdown("---")
    st.markdown("### ⏱️ Null-Minuten-Club")
    nb = df_all[df_all["duration_h"]==0]
    if not nb.empty:
        tn = nb.groupby("user").size().sort_values(ascending=False).head(5)
        st.info(f"**{len(nb):,} Buchungen mit 0 Minuten** – Timer vergessen?\n\n" +
                "  ·  ".join([f"{u} ({n}x)" for u,n in tn.items()]))

    st.markdown("---")
    st.markdown("### 📅 Wochentags-Muster")
    wd_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    wd_de    = ["Mo","Di","Mi","Do","Fr","Sa","So"]
    wd_agg = df_all.groupby("weekday").agg(Stunden=("duration_h","sum")).reindex(wd_order).reset_index()
    wd_agg["Tag"] = wd_de
    fig = px.bar(wd_agg, x="Tag", y="Stunden", text_auto=".0f",
                 color="Stunden", color_continuous_scale="Blues")
    fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("### 💬 Häufigste Wörter in Beschreibungen")
    stopwords = {"und","der","die","das","für","mit","an","auf","in","zu","von","bei","ist","im","am",
                 "ein","eine","einer","einen","des","dem","den","ich","wir","sie","es","er","hat","haben",
                 "the","and","for","with","of","to","a","on","is","nan","","–","-","nicht","auch","noch","wird"}
    txt   = " ".join(df_all["description"].astype(str)).lower()
    words = re.findall(r"\b[a-zäöüß]{3,}\b", txt)
    wf    = Counter(w for w in words if w not in stopwords)
    tw    = pd.DataFrame(wf.most_common(30), columns=["Wort","Häufigkeit"])
    fig   = px.bar(tw.sort_values("Häufigkeit"), x="Häufigkeit", y="Wort",
                   orientation="h", color="Häufigkeit", color_continuous_scale="Blues", text_auto=True)
    fig.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)", height=650)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("⏱️ Clockify Insights · Streamlit & Plotly · Clockify CSV-Export")
