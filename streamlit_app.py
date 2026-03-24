import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="REVOIC · Clockify Insights",
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
        background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
        border-radius: 12px;
        padding: 20px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .metric-card h2 { font-size: 2.2rem; margin: 0; font-weight: 700; }
    .metric-card p  { font-size: 0.9rem; margin: 4px 0 0 0; opacity: 0.85; }
    .section-header {
        font-size: 1.4rem;
        font-weight: 700;
        color: #1e3a5f;
        border-left: 5px solid #2d6a9f;
        padding-left: 12px;
        margin: 24px 0 12px 0;
    }
    .fun-box {
        background: #fff8e1;
        border-left: 5px solid #f9a825;
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
    }
    [data-testid="metric-container"] { background: #f0f4fa; border-radius: 10px; padding: 12px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df['Startdatum'] = pd.to_datetime(df['Startdatum'], dayfirst=True, errors='coerce')
    df['Enddatum']   = pd.to_datetime(df['Enddatum'],   dayfirst=True, errors='coerce')
    df['Jahr']       = df['Startdatum'].dt.year
    df['Monat']      = df['Startdatum'].dt.to_period('M').astype(str)
    df['Quartal']    = df['Startdatum'].dt.to_period('Q').astype(str)
    df['Wochentag']  = df['Startdatum'].dt.day_name()
    df['Stunde']     = df['Startzeit'].str[:2].astype(float, errors='ignore')
    df['Abrechenbar_bool'] = df['Abrechenbar'].str.strip() == 'Ja'
    df['Intern']     = df['Kunde'].str.strip().str.upper() == 'REVOIC'
    df['Dauer (dezimal)'] = pd.to_numeric(df['Dauer (dezimal)'], errors='coerce').fillna(0)
    # Clean up old/ALT projects for display
    df['Projekt_clean'] = df['Projekt'].str.replace(r'^\(Alt\)\s*', '', regex=True).str.strip()
    return df

# ─────────────────────────────────────────────
# SIDEBAR – FILE + FILTERS
# ─────────────────────────────────────────────
st.sidebar.image("https://via.placeholder.com/200x60/1e3a5f/ffffff?text=REVOIC+Insights", width=200)
st.sidebar.title("⚙️ Einstellungen")

uploaded = st.sidebar.file_uploader("📁 Clockify CSV hochladen", type=["csv"])
default_path = "/mnt/data/Clockify_Zeitbericht_Detailliert_01.01.2022-28.02.2026.csv"

if uploaded:
    df_raw = load_data(uploaded)
else:
    df_raw = load_data(default_path)

st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Filter")

years = sorted(df_raw['Jahr'].dropna().unique().astype(int).tolist())
sel_years = st.sidebar.multiselect("Jahr", years, default=years)

users = sorted(df_raw['Benutzer'].dropna().unique().tolist())
sel_users = st.sidebar.multiselect("Mitarbeitende", users, default=users)

clients = sorted(df_raw['Kunde'].dropna().unique().tolist())
sel_clients = st.sidebar.multiselect("Kunden", clients, default=clients)

granularity = st.sidebar.radio("Zeitgranularität", ["Monat", "Quartal", "Jahr"], index=0)
gran_col = {"Monat": "Monat", "Quartal": "Quartal", "Jahr": "Jahr"}[granularity]

# Apply filters
df = df_raw[
    df_raw['Jahr'].isin(sel_years) &
    df_raw['Benutzer'].isin(sel_users) &
    df_raw['Kunde'].isin(sel_clients)
].copy()

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
st.title("⏱️ REVOIC · Clockify Insights")
st.caption(f"Zeitraum: Jan 2022 – Feb 2026  ·  {len(df):,} Einträge nach Filter  ·  {df['Benutzer'].nunique()} Personen  ·  {df['Kunde'].nunique()} Kunden")
st.markdown("---")

# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 Überblick",
    "📈 Entwicklung",
    "👥 Team",
    "🏢 Kunden",
    "🗂️ Projekte",
    "🔄 Intern vs. Extern",
    "🎉 Fun Facts",
])

# ══════════════════════════════════════════════
# TAB 1 – ÜBERBLICK
# ══════════════════════════════════════════════
with tab1:
    st.markdown('<div class="section-header">Key Metrics</div>', unsafe_allow_html=True)

    total_h      = df['Dauer (dezimal)'].sum()
    avg_h_entry  = df['Dauer (dezimal)'].mean()
    bill_pct     = df['Abrechenbar_bool'].mean() * 100
    intern_pct   = df['Intern'].mean() * 100
    num_kunden   = df[~df['Intern']]['Kunde'].nunique()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Gesamtstunden", f"{total_h:,.0f} h")
    c2.metric("Ø pro Eintrag", f"{avg_h_entry:.2f} h")
    c3.metric("Abrechenbar", f"{bill_pct:.1f} %")
    c4.metric("Intern (REVOIC)", f"{intern_pct:.1f} %")
    c5.metric("Aktive Kunden", num_kunden)

    st.markdown('<div class="section-header">Stunden pro Jahr</div>', unsafe_allow_html=True)
    yr_df = df.groupby('Jahr')['Dauer (dezimal)'].sum().reset_index()
    yr_df.columns = ['Jahr', 'Stunden']
    fig = px.bar(yr_df, x='Jahr', y='Stunden', text_auto='.0f',
                 color='Stunden', color_continuous_scale='Blues',
                 labels={'Stunden': 'Stunden (h)'})
    fig.update_layout(coloraxis_showscale=False, xaxis=dict(type='category'))
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="section-header">Top 10 Projekte (Stunden)</div>', unsafe_allow_html=True)
        top_proj = (df.groupby('Projekt')['Dauer (dezimal)'].sum()
                    .sort_values(ascending=False).head(10).reset_index())
        fig2 = px.bar(top_proj, x='Dauer (dezimal)', y='Projekt',
                      orientation='h', text_auto='.0f',
                      color='Dauer (dezimal)', color_continuous_scale='Blues')
        fig2.update_layout(coloraxis_showscale=False, yaxis=dict(autorange='reversed'))
        st.plotly_chart(fig2, use_container_width=True)
    with col2:
        st.markdown('<div class="section-header">Top 10 Kunden (Stunden)</div>', unsafe_allow_html=True)
        top_kd = (df.groupby('Kunde')['Dauer (dezimal)'].sum()
                  .sort_values(ascending=False).head(10).reset_index())
        fig3 = px.bar(top_kd, x='Dauer (dezimal)', y='Kunde',
                      orientation='h', text_auto='.0f',
                      color='Dauer (dezimal)', color_continuous_scale='Teal')
        fig3.update_layout(coloraxis_showscale=False, yaxis=dict(autorange='reversed'))
        st.plotly_chart(fig3, use_container_width=True)

# ══════════════════════════════════════════════
# TAB 2 – ENTWICKLUNG
# ══════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-header">Stunden-Verlauf über Zeit</div>', unsafe_allow_html=True)

    time_df = df.groupby(gran_col)['Dauer (dezimal)'].sum().reset_index()
    time_df.columns = ['Periode', 'Stunden']
    fig = px.area(time_df, x='Periode', y='Stunden',
                  labels={'Stunden': 'Stunden (h)', 'Periode': granularity},
                  color_discrete_sequence=['#2d6a9f'])
    fig.update_xaxes(tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">Abrechenbar vs. Nicht-abrechenbar im Zeitverlauf</div>', unsafe_allow_html=True)
    bill_time = (df.groupby([gran_col, 'Abrechenbar'])['Dauer (dezimal)']
                 .sum().reset_index())
    bill_time.columns = ['Periode', 'Abrechenbar', 'Stunden']
    fig2 = px.bar(bill_time, x='Periode', y='Stunden', color='Abrechenbar',
                  barmode='stack',
                  color_discrete_map={'Ja': '#2d6a9f', 'Nein': '#f0a500'},
                  labels={'Stunden': 'Stunden (h)', 'Periode': granularity})
    fig2.update_xaxes(tickangle=45)
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<div class="section-header">% Abrechenbar pro Periode</div>', unsafe_allow_html=True)
    pct_df = (df.groupby(gran_col)['Abrechenbar_bool']
              .agg(['sum', 'count']).reset_index())
    pct_df.columns = ['Periode', 'Abrechenbar', 'Gesamt']
    pct_df['Pct'] = pct_df['Abrechenbar'] / pct_df['Gesamt'] * 100
    fig3 = px.line(pct_df, x='Periode', y='Pct',
                   labels={'Pct': '% Abrechenbar', 'Periode': granularity},
                   color_discrete_sequence=['#2d6a9f'], markers=True)
    fig3.add_hline(y=pct_df['Pct'].mean(), line_dash='dash', line_color='gray',
                   annotation_text=f"Ø {pct_df['Pct'].mean():.1f}%")
    fig3.update_xaxes(tickangle=45)
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown('<div class="section-header">Neue Kunden pro Jahr (Erstes Tracking)</div>', unsafe_allow_html=True)
    first_seen = (df[~df['Intern']].groupby('Kunde')['Startdatum']
                  .min().dt.year.value_counts().sort_index().reset_index())
    first_seen.columns = ['Jahr', 'Neue Kunden']
    fig4 = px.bar(first_seen, x='Jahr', y='Neue Kunden', text_auto=True,
                  color='Neue Kunden', color_continuous_scale='Blues')
    fig4.update_layout(coloraxis_showscale=False, xaxis=dict(type='category'))
    st.plotly_chart(fig4, use_container_width=True)

# ══════════════════════════════════════════════
# TAB 3 – TEAM
# ══════════════════════════════════════════════
with tab3:
    st.markdown('<div class="section-header">Stunden pro Mitarbeiter:in (gesamt)</div>', unsafe_allow_html=True)

    user_df = (df.groupby('Benutzer')['Dauer (dezimal)'].sum()
               .sort_values(ascending=False).reset_index())
    user_df.columns = ['Person', 'Stunden']
    fig = px.bar(user_df, x='Person', y='Stunden', text_auto='.0f',
                 color='Stunden', color_continuous_scale='Blues')
    fig.update_layout(coloraxis_showscale=False, xaxis_tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">Stunden pro Person im Zeitverlauf (Top 10)</div>', unsafe_allow_html=True)
    top10_users = user_df.head(10)['Person'].tolist()
    user_time = (df[df['Benutzer'].isin(top10_users)]
                 .groupby([gran_col, 'Benutzer'])['Dauer (dezimal)']
                 .sum().reset_index())
    user_time.columns = ['Periode', 'Person', 'Stunden']
    fig2 = px.line(user_time, x='Periode', y='Stunden', color='Person',
                   markers=True,
                   labels={'Stunden': 'Stunden (h)', 'Periode': granularity})
    fig2.update_xaxes(tickangle=45)
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<div class="section-header">% Abrechenbar pro Person</div>', unsafe_allow_html=True)
    user_bill = (df.groupby('Benutzer')
                 .agg(Abrechenbar=('Abrechenbar_bool', 'sum'), Gesamt=('Abrechenbar_bool', 'count'))
                 .reset_index())
    user_bill['Pct_Abrechenbar'] = user_bill['Abrechenbar'] / user_bill['Gesamt'] * 100
    user_bill = user_bill.sort_values('Pct_Abrechenbar', ascending=False)
    fig3 = px.bar(user_bill, x='Benutzer', y='Pct_Abrechenbar',
                  text_auto='.1f',
                  color='Pct_Abrechenbar', color_continuous_scale='RdYlGn',
                  labels={'Pct_Abrechenbar': '% Abrechenbar'})
    fig3.update_layout(coloraxis_showscale=False, xaxis_tickangle=45)
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown('<div class="section-header">Heatmap: Tracking nach Wochentag & Person (Top 8)</div>', unsafe_allow_html=True)
    top8 = user_df.head(8)['Person'].tolist()
    wd_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    wd_labels = ['Mo','Di','Mi','Do','Fr','Sa','So']
    heat_df = (df[df['Benutzer'].isin(top8)]
               .groupby(['Benutzer', 'Wochentag'])['Dauer (dezimal)'].sum()
               .reset_index())
    heat_pivot = heat_df.pivot(index='Benutzer', columns='Wochentag', values='Dauer (dezimal)').fillna(0)
    existing_cols = [c for c in wd_order if c in heat_pivot.columns]
    heat_pivot = heat_pivot[existing_cols]
    fig4 = px.imshow(heat_pivot, color_continuous_scale='Blues',
                     labels={'color': 'Stunden'},
                     aspect='auto')
    st.plotly_chart(fig4, use_container_width=True)

# ══════════════════════════════════════════════
# TAB 4 – KUNDEN
# ══════════════════════════════════════════════
with tab4:
    ext_df = df[~df['Intern']].copy()

    st.markdown('<div class="section-header">Kunden-Entwicklung über Zeit (Top 8)</div>', unsafe_allow_html=True)
    top8_kd = (ext_df.groupby('Kunde')['Dauer (dezimal)'].sum()
               .sort_values(ascending=False).head(8).index.tolist())
    kd_time = (ext_df[ext_df['Kunde'].isin(top8_kd)]
               .groupby([gran_col, 'Kunde'])['Dauer (dezimal)']
               .sum().reset_index())
    kd_time.columns = ['Periode', 'Kunde', 'Stunden']
    fig = px.line(kd_time, x='Periode', y='Stunden', color='Kunde',
                  markers=True,
                  labels={'Stunden': 'Stunden (h)', 'Periode': granularity})
    fig.update_xaxes(tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">Langzeit-Kunden: Wie lange dabei?</div>', unsafe_allow_html=True)
    kd_span = (ext_df.groupby('Kunde')['Startdatum']
               .agg(['min', 'max']).reset_index())
    kd_span.columns = ['Kunde', 'Erste Buchung', 'Letzte Buchung']
    kd_span['Tage aktiv'] = (kd_span['Letzte Buchung'] - kd_span['Erste Buchung']).dt.days
    kd_span['Monate aktiv'] = (kd_span['Tage aktiv'] / 30).round(1)
    kd_stunden = ext_df.groupby('Kunde')['Dauer (dezimal)'].sum().reset_index()
    kd_stunden.columns = ['Kunde', 'Stunden gesamt']
    kd_span = kd_span.merge(kd_stunden, on='Kunde').sort_values('Monate aktiv', ascending=False)

    fig2 = px.scatter(kd_span, x='Monate aktiv', y='Stunden gesamt',
                      size='Stunden gesamt', color='Stunden gesamt',
                      hover_name='Kunde', color_continuous_scale='Blues',
                      labels={'Monate aktiv': 'Monate aktiv', 'Stunden gesamt': 'Stunden'},
                      size_max=60)
    fig2.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<div class="section-header">Kunden-Tabelle (sortierbar)</div>', unsafe_allow_html=True)
    st.dataframe(
        kd_span[['Kunde', 'Erste Buchung', 'Letzte Buchung', 'Monate aktiv', 'Stunden gesamt']]
        .assign(**{'Erste Buchung': lambda x: x['Erste Buchung'].dt.date,
                   'Letzte Buchung': lambda x: x['Letzte Buchung'].dt.date})
        .style.background_gradient(subset=['Stunden gesamt', 'Monate aktiv'], cmap='Blues'),
        use_container_width=True, height=400
    )

    st.markdown('<div class="section-header">Einzelnen Kunden analysieren</div>', unsafe_allow_html=True)
    sel_kd = st.selectbox("Kunde auswählen", sorted(ext_df['Kunde'].unique().tolist()))
    kd_detail = ext_df[ext_df['Kunde'] == sel_kd]
    c1, c2, c3 = st.columns(3)
    c1.metric("Gesamt-Stunden", f"{kd_detail['Dauer (dezimal)'].sum():.1f} h")
    c2.metric("Einträge", f"{len(kd_detail):,}")
    c3.metric("Aktive Monate", f"{kd_detail['Monat'].nunique()}")

    kd_proj = (kd_detail.groupby('Projekt')['Dauer (dezimal)'].sum()
               .sort_values(ascending=False).reset_index())
    fig3 = px.pie(kd_proj, names='Projekt', values='Dauer (dezimal)',
                  title=f'Projektverteilung – {sel_kd}',
                  color_discrete_sequence=px.colors.sequential.Blues_r)
    st.plotly_chart(fig3, use_container_width=True)

    kd_trend = (kd_detail.groupby('Monat')['Dauer (dezimal)'].sum().reset_index())
    kd_trend.columns = ['Monat', 'Stunden']
    fig4 = px.bar(kd_trend, x='Monat', y='Stunden',
                  title=f'Monatliche Stunden – {sel_kd}',
                  color='Stunden', color_continuous_scale='Blues')
    fig4.update_layout(coloraxis_showscale=False, xaxis_tickangle=45)
    st.plotly_chart(fig4, use_container_width=True)

# ══════════════════════════════════════════════
# TAB 5 – PROJEKTE
# ══════════════════════════════════════════════
with tab5:
    st.markdown('<div class="section-header">Projektmix über Zeit (%)</div>', unsafe_allow_html=True)

    # Top 10 Projekte, Rest = "Sonstiges"
    top10_proj = (df.groupby('Projekt')['Dauer (dezimal)'].sum()
                  .sort_values(ascending=False).head(10).index.tolist())
    df_proj_tmp = df.copy()
    df_proj_tmp['Projekt_grp'] = df_proj_tmp['Projekt'].apply(
        lambda x: x if x in top10_proj else 'Sonstiges')
    proj_time = (df_proj_tmp.groupby([gran_col, 'Projekt_grp'])['Dauer (dezimal)']
                 .sum().reset_index())
    proj_time.columns = ['Periode', 'Projekt', 'Stunden']
    proj_total = proj_time.groupby('Periode')['Stunden'].transform('sum')
    proj_time['Anteil (%)'] = proj_time['Stunden'] / proj_total * 100
    fig = px.bar(proj_time, x='Periode', y='Anteil (%)', color='Projekt',
                 barmode='stack',
                 labels={'Anteil (%)': 'Anteil in %', 'Periode': granularity})
    fig.update_xaxes(tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">ALT-Projekte: Aufräum-Trend</div>', unsafe_allow_html=True)
    df['ist_alt'] = df['Projekt'].str.startswith('(Alt)') | df['Projekt'].str.contains('ALT', case=False, na=False)
    alt_time = (df.groupby([gran_col, 'ist_alt'])['Dauer (dezimal)']
                .sum().reset_index())
    alt_time.columns = ['Periode', 'ALT-Projekt', 'Stunden']
    alt_time['Label'] = alt_time['ALT-Projekt'].map({True: 'ALT / veraltet', False: 'Aktuell'})
    fig2 = px.bar(alt_time, x='Periode', y='Stunden', color='Label',
                  barmode='stack',
                  color_discrete_map={'ALT / veraltet': '#e57373', 'Aktuell': '#2d6a9f'},
                  labels={'Stunden': 'Stunden (h)', 'Periode': granularity})
    fig2.update_xaxes(tickangle=45)
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<div class="section-header">Vollständige Projektübersicht</div>', unsafe_allow_html=True)
    proj_sum = (df.groupby('Projekt')
                .agg(Stunden=('Dauer (dezimal)', 'sum'),
                     Einträge=('Dauer (dezimal)', 'count'),
                     Ø_Dauer=('Dauer (dezimal)', 'mean'),
                     Abrechenbar=('Abrechenbar_bool', 'mean'))
                .reset_index()
                .sort_values('Stunden', ascending=False))
    proj_sum['Abrechenbar'] = (proj_sum['Abrechenbar'] * 100).round(1).astype(str) + ' %'
    proj_sum['Ø_Dauer'] = proj_sum['Ø_Dauer'].round(2)
    st.dataframe(proj_sum, use_container_width=True, height=500)

# ══════════════════════════════════════════════
# TAB 6 – INTERN vs. EXTERN
# ══════════════════════════════════════════════
with tab6:
    st.markdown('<div class="section-header">Intern vs. Extern im Zeitverlauf</div>', unsafe_allow_html=True)

    ie_df = df.copy()
    ie_df['Typ_IE'] = ie_df['Intern'].map({True: '🏠 Intern (REVOIC)', False: '🏢 Extern (Kunden)'})
    ie_time = (ie_df.groupby([gran_col, 'Typ_IE'])['Dauer (dezimal)']
               .sum().reset_index())
    ie_time.columns = ['Periode', 'Typ', 'Stunden']
    fig = px.bar(ie_time, x='Periode', y='Stunden', color='Typ',
                 barmode='stack',
                 color_discrete_map={'🏠 Intern (REVOIC)': '#f0a500', '🏢 Extern (Kunden)': '#2d6a9f'},
                 labels={'Stunden': 'Stunden (h)', 'Periode': granularity})
    fig.update_xaxes(tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">% Interne Zeit pro Periode</div>', unsafe_allow_html=True)
    ie_pct = (ie_df.groupby(gran_col)['Intern']
              .agg(['sum', 'count']).reset_index())
    ie_pct.columns = ['Periode', 'Intern', 'Gesamt']
    ie_pct['% Intern'] = ie_pct['Intern'] / ie_pct['Gesamt'] * 100
    fig2 = px.line(ie_pct, x='Periode', y='% Intern',
                   markers=True, color_discrete_sequence=['#f0a500'],
                   labels={'% Intern': '% Interne Einträge', 'Periode': granularity})
    fig2.add_hline(y=ie_pct['% Intern'].mean(), line_dash='dash', line_color='gray',
                   annotation_text=f"Ø {ie_pct['% Intern'].mean():.1f}%")
    fig2.update_xaxes(tickangle=45)
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<div class="section-header">Interne Projekte: Wie hat sich der Mix verändert?</div>', unsafe_allow_html=True)
    int_df = df[df['Intern']].copy()
    top8_int = (int_df.groupby('Projekt')['Dauer (dezimal)'].sum()
                .sort_values(ascending=False).head(8).index.tolist())
    int_df['Projekt_grp'] = int_df['Projekt'].apply(
        lambda x: x if x in top8_int else 'Sonstiges')
    int_time = (int_df.groupby([gran_col, 'Projekt_grp'])['Dauer (dezimal)']
                .sum().reset_index())
    int_time.columns = ['Periode', 'Projekt', 'Stunden']
    int_total = int_time.groupby('Periode')['Stunden'].transform('sum')
    int_time['Anteil (%)'] = int_time['Stunden'] / int_total * 100
    fig3 = px.bar(int_time, x='Periode', y='Anteil (%)', color='Projekt',
                  barmode='stack',
                  labels={'Anteil (%)': 'Anteil in %', 'Periode': granularity})
    fig3.update_xaxes(tickangle=45)
    st.plotly_chart(fig3, use_container_width=True)

# ══════════════════════════════════════════════
# TAB 7 – FUN FACTS 🎉
# ══════════════════════════════════════════════
with tab7:
    st.markdown('<div class="section-header">🎉 Fun Facts & kuriose Einblicke</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        # Früheste Buchung des Tages
        df_hr = df.copy()
        df_hr['Stunde_num'] = pd.to_numeric(df['Startzeit'].str[:2], errors='coerce')
        early = df_hr[df_hr['Stunde_num'] < 6].copy()
        night = df_hr[df_hr['Stunde_num'] >= 22].copy()

        st.markdown(f"""
        <div class="fun-box">
        🌅 <b>Frühaufsteher:</b> {len(early):,} Einträge vor 6 Uhr morgens!<br>
        🦉 <b>Nachteulen:</b> {len(night):,} Einträge nach 22 Uhr!
        </div>""", unsafe_allow_html=True)

        # Kürzeste Buchung
        shortest = df.nsmallest(1, 'Dauer (dezimal)')
        st.markdown(f"""
        <div class="fun-box">
        ⚡ <b>Kürzeste Buchung:</b> {shortest['Dauer (dezimal)'].values[0]:.3f} h ({shortest['Dauer (dezimal)'].values[0]*60:.0f} Min)
        – von <i>{shortest['Benutzer'].values[0]}</i> für <i>{shortest['Kunde'].values[0]}</i>
        </div>""", unsafe_allow_html=True)

        # Längste Buchung
        longest = df.nlargest(1, 'Dauer (dezimal)')
        st.markdown(f"""
        <div class="fun-box">
        🏋️ <b>Längste Einzelbuchung:</b> {longest['Dauer (dezimal)'].values[0]:.1f} h
        – von <i>{longest['Benutzer'].values[0]}</i> am <i>{str(longest['Startdatum'].values[0])[:10]}</i>
        <br>📝 "{longest['Beschreibung'].values[0]}"
        </div>""", unsafe_allow_html=True)

    with col2:
        # Produktivster Tag
        best_day = (df.groupby('Startdatum')['Dauer (dezimal)'].sum()
                    .idxmax())
        best_day_h = df.groupby('Startdatum')['Dauer (dezimal)'].sum().max()
        st.markdown(f"""
        <div class="fun-box">
        🏆 <b>Produktivster Tag:</b> {str(best_day)[:10]} mit {best_day_h:.1f} Stunden (Team gesamt)
        </div>""", unsafe_allow_html=True)

        # Wochenend-Warriors
        df['ist_wochenende'] = df['Wochentag'].isin(['Saturday', 'Sunday'])
        we = df[df['ist_wochenende']]
        we_top = we.groupby('Benutzer')['Dauer (dezimal)'].sum().sort_values(ascending=False).head(3)
        we_str = ", ".join([f"{u} ({h:.0f}h)" for u, h in we_top.items()])
        st.markdown(f"""
        <div class="fun-box">
        🛡️ <b>Wochenend-Warriors (Top 3):</b><br>{we_str}
        </div>""", unsafe_allow_html=True)

        # Meiste Einträge an einem Tag
        busy_person = (df.groupby(['Benutzer', 'Startdatum'])
                       .size().idxmax())
        busy_count  = df.groupby(['Benutzer', 'Startdatum']).size().max()
        st.markdown(f"""
        <div class="fun-box">
        📋 <b>Meiste Buchungen an einem Tag:</b> {busy_count} Einträge
        – von <i>{busy_person[0]}</i> am <i>{str(busy_person[1])[:10]}</i>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-header">⏰ Wann wird am meisten gebucht? (Stunde des Tages)</div>', unsafe_allow_html=True)
    df_hr2 = df.copy()
    df_hr2['Stunde_num'] = pd.to_numeric(df['Startzeit'].str[:2], errors='coerce')
    hour_df = df_hr2.groupby('Stunde_num')['Dauer (dezimal)'].sum().reset_index()
    hour_df.columns = ['Stunde', 'Stunden']
    fig = px.bar(hour_df, x='Stunde', y='Stunden',
                 color='Stunden', color_continuous_scale='Blues',
                 labels={'Stunde': 'Uhrzeit (Stunde)', 'Stunden': 'Stunden (h)'})
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">📅 Wochentags-Muster: Wann arbeitet das Team?</div>', unsafe_allow_html=True)
    wd_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    wd_labels_map = {'Monday':'Mo','Tuesday':'Di','Wednesday':'Mi',
                     'Thursday':'Do','Friday':'Fr','Saturday':'Sa','Sunday':'So'}
    wd_df = (df.groupby('Wochentag')['Dauer (dezimal)'].sum()
             .reindex(wd_order).reset_index())
    wd_df.columns = ['Tag', 'Stunden']
    wd_df['Tag_DE'] = wd_df['Tag'].map(wd_labels_map)
    fig2 = px.bar(wd_df, x='Tag_DE', y='Stunden',
                  color='Stunden', color_continuous_scale='Blues',
                  labels={'Tag_DE': 'Wochentag', 'Stunden': 'Stunden (h)'})
    fig2.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<div class="section-header">🔤 Häufigste Begriffe in Beschreibungen</div>', unsafe_allow_html=True)
    from collections import Counter
    import re
    all_desc = ' '.join(df['Beschreibung'].dropna().str.lower().tolist())
    words = re.findall(r'\b[a-zäöüß]{4,}\b', all_desc)
    stopwords = {'und','mit','der','die','das','für','von','ist','eine','ein',
                 'nicht','auch','sich','sind','wird','haben','nach','aber',
                 'oder','beim','wurde','noch','dem','alle','this','that'}
    word_freq = Counter(w for w in words if w not in stopwords)
    top_words = pd.DataFrame(word_freq.most_common(20), columns=['Wort', 'Häufigkeit'])
    fig3 = px.bar(top_words, x='Häufigkeit', y='Wort', orientation='h',
                  color='Häufigkeit', color_continuous_scale='Blues')
    fig3.update_layout(coloraxis_showscale=False, yaxis=dict(autorange='reversed'))
    st.plotly_chart(fig3, use_container_width=True)

# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.markdown("---")
st.caption("REVOIC Clockify Insights · Gebaut mit ❤️ und Streamlit · Daten: Jan 2022 – Feb 2026")

