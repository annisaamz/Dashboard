# -*- coding: utf-8 -*-
"""
Dashboard Pengurangan Kemacetan Kota Surabaya (etl-streaming-2) — Light Mode, v2
Jalankan dari folder project:  streamlit run dashboard_traffic_surabaya.py

Dashboard standalone: hanya membaca file CSV (tanpa koneksi ke ETL/database).

Struktur:
  dashboard/
  ├── dashboard_traffic_surabaya.py
  └── data/            <- taruh semua CSV di sini
Fallback pencarian CSV: data/, folder script, dashboard/ di sebelah script.
Opsional: env DASHBOARD_DATA_DIR untuk memaksa folder data.

Nama file dikenali dengan pola  <prefix>.csv  atau  <prefix>_<timestamp>.csv  (prefix harus persis,
jadi traffic_flow tidak tertukar dengan traffic_flow_regular).
"""
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Dashboard Kemacetan Surabaya", page_icon="🚦", layout="wide")

# ----------------------------------------------------------------------------
# KONFIGURASI
# ----------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
SEARCH_DIRS = [SCRIPT_DIR / "data", SCRIPT_DIR, SCRIPT_DIR / "dashboard"]
if os.environ.get("DASHBOARD_DATA_DIR"):
    SEARCH_DIRS.insert(0, Path(os.environ["DASHBOARD_DATA_DIR"]))

DATASETS = ["monitoring_points", "traffic_flow", "traffic_flow_regular", "traffic_hourly", "traffic_incidents",
            "traffic_forecast", "mart_traffic_features", "weather_hourly", "air_quality_hourly"]
MULTI = {"traffic_flow"}  # semua file yang cocok digabung (mis. simulator + tomtom); lainnya: ambil terbaru
TZ = "Asia/Jakarta"          # semua waktu ditampilkan dalam WIB
TARGET_REDUCTION = 0.15
LEVELS = ["LANCAR", "PADAT", "MACET"]
LEVEL_COLORS = {"LANCAR": "#22c55e", "PADAT": "#f59e0b", "MACET": "#ef4444"}
# Ambang level diturunkan dari rentang congestion_index per level pada traffic_flow:
# LANCAR <= 0.20 < PADAT <= 0.50 < MACET
LEVEL_BINS = [-np.inf, 20, 50, np.inf]
MAG_ORDER = ["Ringan", "Sedang", "Berat", "Tidak terdefinisi"]
MAG_COLORS = {"Ringan": "#f59e0b", "Sedang": "#f97316", "Berat": "#ef4444", "Tidak terdefinisi": "#94a3b8"}
CONG_SCALE = [[0, "#22c55e"], [0.45, "#facc15"], [1, "#ef4444"]]
COLORWAY = ["#2563eb", "#f59e0b", "#10b981", "#8b5cf6", "#ef4444", "#06b6d4", "#ec4899", "#64748b"]
ENV_LABELS = {
    "temperature": "Temperature (°C)", "relative_humidity": "Kelembapan (%)", "wind_speed": "Kecepatan angin",
    "pm2_5": "PM2.5 (µg/m³)", "pm10": "PM10 (µg/m³)", "nitrogen_dioxide": "NO₂ (µg/m³)",
    "carbon_monoxide": "CO (µg/m³)", "us_aqi": "US AQI",
}

st.markdown(
    """
<style>

/* =========================================================
   GLOBAL LIGHT THEME
   ========================================================= */

.stApp {
    background-color: #f8fafc !important;
    color: #0f172a !important;
}

.block-container {
    padding-top: 1.4rem;
    max-width: 1500px;
}


/* =========================================================
   GLOBAL TEXT
   ========================================================= */

h1, h2, h3, h4, h5, h6 {
    color: #0f172a !important;
}

p {
    color: #0f172a;
}

/* Markdown text */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span {
    color: #0f172a;
}

/* Caption */
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {
    color: #64748b !important;
}


/* =========================================================
   SIDEBAR
   ========================================================= */

section[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e2e8f0;
}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] h4,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span {
    color: #0f172a !important;
}


/* Sidebar radio */
section[data-testid="stSidebar"] [data-testid="stRadio"] label {
    color: #0f172a !important;
}


/* Sidebar selectbox / multiselect */
section[data-testid="stSidebar"] [data-baseweb="select"] {
    color: #0f172a !important;
}

section[data-testid="stSidebar"] [data-baseweb="select"] * {
    color: #0f172a !important;
}


/* Sidebar slider */
section[data-testid="stSidebar"] [data-testid="stSlider"] {
    color: #0f172a !important;
}


/* Sidebar checkbox */
section[data-testid="stSidebar"] [data-testid="stCheckbox"] label {
    color: #0f172a !important;
}


/* =========================================================
   INPUT / WIDGET
   ========================================================= */

[data-baseweb="select"] {
    background-color: #ffffff !important;
}

[data-baseweb="select"] * {
    color: #0f172a !important;
}

input,
textarea {
    color: #0f172a !important;
    background-color: #ffffff !important;
}


/* =========================================================
   KPI CARDS
   ========================================================= */

.kpi {
    background: #ffffff !important;
    border: 1px solid #e2e8f0;
    border-left: 5px solid #2563eb;
    border-radius: 10px;
    padding: 12px 14px;
    box-shadow: 0 1px 3px rgba(15,23,42,.06);
    min-height: 98px;
}

.kpi-label {
    color: #64748b !important;
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .05em;
    font-weight: 600;
}

.kpi-value {
    color: #0f172a !important;
    font-size: 1.55rem;
    font-weight: 700;
    line-height: 1.3;
}

.kpi-sub {
    color: #94a3b8 !important;
    font-size: .75rem;
}


/* =========================================================
   INSIGHT BOX
   ========================================================= */

.insight {
    background: #eff6ff !important;
    border: 1px solid #bfdbfe;
    border-radius: 10px;
    padding: 10px 18px;
    color: #1e3a8a !important;
}

.insight li,
.insight p,
.insight span {
    color: #1e3a8a !important;
}


/* =========================================================
   STREAMLIT ALERTS
   ========================================================= */

/* Info */
[data-testid="stAlert"] {
    color: #0f172a !important;
}

[data-testid="stAlert"] p,
[data-testid="stAlert"] span {
    color: inherit !important;
}


/* =========================================================
   METRICS
   ========================================================= */

[data-testid="stMetricLabel"] {
    color: #64748b !important;
}

[data-testid="stMetricValue"] {
    color: #0f172a !important;
}

[data-testid="stMetricDelta"] {
    color: #475569 !important;
}


/* =========================================================
   TABS
   ========================================================= */

button[data-baseweb="tab"] {
    color: #475569 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #2563eb !important;
}


/* =========================================================
   EXPANDER
   ========================================================= */

[data-testid="stExpander"] {
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0;
}

[data-testid="stExpander"] summary {
    color: #0f172a !important;
}

[data-testid="stExpander"] summary span {
    color: #0f172a !important;
}


/* =========================================================
   DATAFRAME / TABLE
   ========================================================= */

[data-testid="stDataFrame"] {
    background-color: #ffffff !important;
}


/* =========================================================
   BUTTON
   ========================================================= */

.stButton button {
    color: #0f172a !important;
    background-color: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
}


/* =========================================================
   PROGRESS BAR
   ========================================================= */

[data-testid="stProgress"] {
    color: #2563eb !important;
}

</style>
""",
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------------
# UTILITAS
# ----------------------------------------------------------------------------
def find_files(prefix):
    """File yang cocok persis  <prefix>.csv  /  <prefix>_<8-14 digit>.csv ; terbaru (mtime) lebih dulu."""
    pat = re.compile(rf"^{re.escape(prefix)}(?:_\d{{8,14}})?\.csv$")
    found = {}
    for d in SEARCH_DIRS:
        if d.is_dir():
            for p in d.iterdir():
                if pat.match(p.name):
                    found[p.resolve()] = p.resolve()
    return sorted(found.values(), key=lambda p: (p.stat().st_mtime, p.name), reverse=True)


def parse_ts(s):
    """Parse timestamp ber-offset (UTC '+00' / WIB '+0700') -> WIB tanpa tz."""
    dt = pd.to_datetime(s, errors="coerce", utc=True, format="mixed")
    return dt.dt.tz_convert(TZ).dt.tz_localize(None)


def to_bool(s):
    return s.astype(str).str.strip().str.lower().isin(["true", "1", "t", "yes"])


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def level_from_pct(s):
    return pd.cut(s, LEVEL_BINS, labels=LEVELS).astype(str)


def pchart(fig, key=None, height=None):
    fig.update_layout(template="plotly_white", paper_bgcolor="white", plot_bgcolor="white",
                      font=dict(color="#0f172a"), colorway=COLORWAY, margin=dict(l=10, r=10, t=40, b=10))
    if height:
        fig.update_layout(height=height)
    try:
        st.plotly_chart(fig, width="stretch", key=key)
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=key)


def show_df(df, **kw):
    try:
        st.dataframe(df, width="stretch", hide_index=True, **kw)
    except TypeError:
        st.dataframe(df, use_container_width=True, hide_index=True, **kw)


ACCENTS = ["#2563eb", "#0ea5e9", "#f59e0b", "#f97316", "#ef4444", "#8b5cf6"]


def kpi_row(items):
    for i, (col, (label, value, sub)) in enumerate(zip(st.columns(len(items)), items)):
        col.markdown(
            f'<div class="kpi" style="border-left-color:{ACCENTS[i % len(ACCENTS)]}">'
            f'<div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>'
            f'<div class="kpi-sub">{sub}</div></div>', unsafe_allow_html=True)
    st.write("")


def fmt(x, nd=1, suffix=""):
    return "–" if x is None or pd.isna(x) else f"{x:,.{nd}f}{suffix}"


def header(title, caption, tf=None):
    st.title(title)
    st.caption(caption)
    

def make_map(df, color, size, custom_data, hovertemplate, zoom=10.3, height=520, **kw):
    use_new = hasattr(px, "scatter_map")
    fn = px.scatter_map if use_new else px.scatter_mapbox
    style = {"map_style": "open-street-map"} if use_new else {"mapbox_style": "open-street-map"}
    fig = fn(df, lat="latitude", lon="longitude", color=color, size=size, size_max=26,
             custom_data=custom_data, zoom=zoom, height=height, **style, **kw)
    fig.update_traces(hovertemplate=hovertemplate)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    return fig


def spread_note(a, col="avg_congestion"):
    """Peringatan jika rata-rata antar titik nyaris identik (ranking titik tidak informatif)."""
    if len(a) > 1 and (a[col].max() - a[col].min()) < 2.0:
        st.info(f"Rata-rata congestion antar titik nyaris identik (selisih {a[col].max() - a[col].min():.2f} poin "
                "persentase). Peringkat titik kurang informatif; pola waktu (jam) lebih bermakna.")


# ----------------------------------------------------------------------------
# LOAD & PREPARE
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner="Memuat data...")
def load_all(file_map):
    data, meta = {}, {}
    raw = {}
    for k, paths in file_map.items():
        frames = [pd.read_csv(p) for p, _ in paths]
        raw[k] = frames
        meta[k] = {"files": [Path(p).name for p, _ in paths], "rows": int(sum(len(f) for f in frames)),
                   "cols": int(max(f.shape[1] for f in frames))}

    mp = raw["monitoring_points"][0].copy()
    data["monitoring_points"] = mp
    mpj = mp.rename(columns={"name": "location"})[["point_id", "corridor", "location", "latitude", "longitude"]]

    def attach(df):
        df = df.drop(columns=[c for c in ["corridor", "location", "latitude", "longitude"] if c in df.columns])
        df = df.merge(mpj, on="point_id", how="left")
        df["corridor"] = df["corridor"].fillna("Tidak diketahui")
        df["location"] = df["location"].fillna(df["point_id"])
        df["point_label"] = df["point_id"] + " — " + df["location"]
        return df

        # --- traffic_flow (gabungan semua file; kolom waktu timestamp_utc atau observed_at)
    parts = []
    for d in raw["traffic_flow"]:
        d = d.copy()
        tcol = "timestamp_utc" if "timestamp_utc" in d.columns else "observed_at"
        d["ts"] = parse_ts(d[tcol])
        parts.append(d)

    tf = pd.concat(parts, ignore_index=True)

    # Semua CSV traffic_flow yang digunakan dashboard merupakan
    # data statis yang berasal dari TomTom.
    tf["source"] = "tomtom"

    for c in ["current_speed", "free_flow_speed", "current_travel_time", "free_flow_travel_time",
              "speed_ratio", "congestion_index", "delay_seconds"]:
        tf[c] = pd.to_numeric(tf[c], errors="coerce")
    tf["speed_ratio"] = tf["speed_ratio"].fillna(
        tf["current_speed"] / tf["free_flow_speed"])
    tf["congestion_index"] = tf["congestion_index"].fillna(
        1 - tf["speed_ratio"])
    tf["delay_seconds"] = tf["delay_seconds"].fillna(
        tf["current_travel_time"] - tf["free_flow_travel_time"])
    tf = tf.dropna(subset=["ts", "point_id"]).drop_duplicates(["ts", "point_id", "source"])
    tf["congestion_pct"] = tf["congestion_index"] * 100
    if "congestion_level" in tf.columns:
        tf["congestion_level"] = tf["congestion_level"].astype(str).str.upper()
    else:
        tf["congestion_level"] = level_from_pct(tf["congestion_pct"])
    tf["date"] = tf["ts"].dt.date
    tf["hour"] = tf["ts"].dt.hour
    tf["hour_label"] = tf["hour"].map(lambda h: f"{h:02d}:00")
    tf["hour_ts"] = tf["ts"].dt.floor("60min")
    data["traffic_flow"] = attach(tf)

    # --- traffic_flow_regular (grid 10 menit, ada gap/filled)
    if "traffic_flow_regular" in raw:
        rg = raw["traffic_flow_regular"][0].copy()
        rg["ts"] = parse_ts(rg["timestamp_utc"])
        for c in ["is_gap", "is_filled"]:
            if c in rg.columns:
                rg[c] = to_bool(rg[c])
        rg["congestion_pct"] = pd.to_numeric(rg["congestion_index"], errors="coerce") * 100
        rg["date"] = rg["ts"].dt.date
        data["traffic_flow_regular"] = attach(rg)

    # --- traffic_hourly
    if "traffic_hourly" in raw:
        th = raw["traffic_hourly"][0].copy()
        tcol = "hour_utc" if "hour_utc" in th.columns else "hour"
        th["hour_ts"] = parse_ts(th[tcol])
        data["traffic_hourly"] = attach(th)

    # --- mart_traffic_features
    if "mart_traffic_features" in raw:
        m = raw["mart_traffic_features"][0].copy()
        m["hour_ts"] = parse_ts(m["hour"])
        m["date"] = m["hour_ts"].dt.date
        data["mart_traffic_features"] = attach(m)

    # --- forecast
    if "traffic_forecast" in raw:
        fc = raw["traffic_forecast"][0].copy()
        fc["hour_ts"] = parse_ts(fc["target_hour"])
        fc["created_ts"] = parse_ts(fc["created_at"])
        fc["predicted_pct"] = fc["predicted_congestion"] * 100
        fc["horizon_h"] = (fc["hour_ts"] - fc["created_ts"]).dt.total_seconds() / 3600
        fc["date"] = fc["hour_ts"].dt.date
        data["traffic_forecast"] = attach(fc)

    # --- incidents (+ titik monitoring terdekat)
    if "traffic_incidents" in raw:
        inc = raw["traffic_incidents"][0].copy()
        for c in ["start_time", "end_time", "first_seen_at", "last_seen_at"]:
            inc[c] = parse_ts(inc[c])
        inc["first_date"] = inc["first_seen_at"].dt.date
        inc["first_hour"] = inc["first_seen_at"].dt.hour
        dist = haversine_km(inc["latitude"].to_numpy()[:, None], inc["longitude"].to_numpy()[:, None],
                            mp["latitude"].to_numpy()[None, :], mp["longitude"].to_numpy()[None, :])
        inc["nearest_point"] = mp["point_id"].to_numpy()[dist.argmin(axis=1)]
        inc["nearest_km"] = dist.min(axis=1)
        inc["road"] = inc["road_from"].fillna("?") + " → " + inc["road_to"].fillna("?")
        data["traffic_incidents"] = inc

    # --- weather & air quality
    for k in ["weather_hourly", "air_quality_hourly"]:
        if k in raw:
            df = raw[k][0].copy()
            df["hour_ts"] = parse_ts(df["observed_hour"])
            df["is_forecast"] = to_bool(df["is_forecast"])
            data[k] = df
    return data, meta


def hourly_points(tf, min_samples=1):
    """Agregasi per titik-jam dari traffic_flow mentah (sumber utama analisis per jam)."""
    g = tf.groupby(["point_id", "point_label", "location", "corridor", "hour_ts"], dropna=False).agg(
        congestion_pct=("congestion_pct", "mean"), max_congestion=("congestion_pct", "max"),
        delay=("delay_seconds", "mean"), speed=("current_speed", "mean"),
        samples=("point_id", "size")).reset_index()
    g = g[g["samples"] >= min_samples].copy()
    g["hour"] = g["hour_ts"].dt.hour
    g["hour_label"] = g["hour"].map(lambda h: f"{h:02d}:00")
    g["date"] = g["hour_ts"].dt.date
    return g


def agg_points(tf):
    return tf.groupby(["point_id", "point_label", "location", "corridor", "latitude", "longitude"], dropna=False).agg(
        avg_congestion=("congestion_pct", "mean"), max_congestion=("congestion_pct", "max"),
        avg_delay=("delay_seconds", "mean"), avg_speed=("current_speed", "mean"),
        avg_free_flow=("free_flow_speed", "mean"), observations=("point_id", "size"),
        pct_macet=("congestion_level", lambda s: (s == "MACET").mean() * 100)).reset_index()


# ----------------------------------------------------------------------------
# SIDEBAR & FILTER
# ----------------------------------------------------------------------------
def sidebar_filters(tf):
    st.sidebar.markdown("### 🔎 Filter Global")
    base = tf
    dmin = base["date"].min() if len(base) else tf["date"].min()
    dmax = base["date"].max() if len(base) else tf["date"].max()
    rng = st.sidebar.date_input("Rentang tanggal (WIB)", value=(dmin, dmax), min_value=dmin, max_value=dmax,
                                key=f"date_{dmin}_{dmax}")
    if isinstance(rng, (tuple, list)):
        d0, d1 = (rng[0], rng[1]) if len(rng) == 2 else (rng[0], rng[0])
    else:
        d0 = d1 = rng
    corridors = sorted(tf["corridor"].unique())
    sel_cor = st.sidebar.multiselect("Koridor", corridors, default=corridors)
    pts = tf[tf["corridor"].isin(sel_cor)][["point_id", "point_label"]].drop_duplicates().sort_values("point_id")
    labels = dict(zip(pts["point_id"], pts["point_label"]))
    sel_pts = st.sidebar.multiselect("Titik monitoring", list(labels), default=list(labels),
                                     format_func=lambda x: labels[x])
    levels = [l for l in LEVELS if l in set(tf["congestion_level"])] + \
             sorted(set(tf["congestion_level"]) - set(LEVELS))
    sel_lvl = st.sidebar.multiselect("Level kemacetan", levels, default=levels,
                                     help="Memfilter baris observasi sebelum dirata-rata, sehingga rata-rata hanya "
                                          "mencerminkan level terpilih.")
    min_s = st.sidebar.slider("Minimum sampel per titik-jam", 1, 30, 5,
                              help="Dipakai pada agregasi per jam (Environment, Forecast, boxplot) agar jam dengan "
                                   "sampel sangat sedikit tidak menyesatkan.")
    st.sidebar.markdown("---")
    inc_apply = st.sidebar.checkbox("Terapkan filter koridor/titik ke incident", value=False,
                                    help="Incident dipetakan ke titik monitoring terdekat. Default: hanya filter tanggal.")
    radius = st.sidebar.slider("Radius incident ke titik (km)", 0.5, 10.0, 2.0, 0.5, disabled=not inc_apply)
    return dict(d0=d0, d1=d1, cor=sel_cor, pts=sel_pts, lvl=sel_lvl, min_s=min_s,
            inc_apply=inc_apply, radius=radius)


def apply_filters(tf, f, use_level=True):
    m = (tf["date"].between(f["d0"], f["d1"])
         & tf["corridor"].isin(f["cor"]) & tf["point_id"].isin(f["pts"]))
    if use_level:
        m &= tf["congestion_level"].isin(f["lvl"])
    return tf[m].copy()


def apply_point_filters(df, f, date_col="date"):
    if df is None:
        return None
    m = df[date_col].between(f["d0"], f["d1"]) & df["corridor"].isin(f["cor"]) & df["point_id"].isin(f["pts"])
    return df[m].copy()


def filter_incidents(inc, f):
    if inc is None:
        return None
    m = inc["first_date"].between(f["d0"], f["d1"])
    if f["inc_apply"]:
        m &= inc["nearest_point"].isin(f["pts"]) & (inc["nearest_km"] <= f["radius"])
    return inc[m].copy()


# ----------------------------------------------------------------------------
# PAGE 1 — EXECUTIVE OVERVIEW
# ----------------------------------------------------------------------------
def auto_insights(tf):
    hh = tf.groupby("hour_label").agg(c=("congestion_pct", "mean"), d=("delay_seconds", "mean"))
    top = hh["c"].sort_values(ascending=False).head(3)
    lines = ["Jam dengan rata-rata congestion tertinggi (WIB): "
             + ", ".join(f"<b>{h}</b> ({v:.1f}%)" for h, v in top.items())
             + f"; terendah: <b>{hh['c'].idxmin()}</b> ({hh['c'].min():.1f}%)."]
    lines.append(f"Delay rata-rata tertinggi terjadi pada <b>{hh['d'].idxmax()}</b> ({hh['d'].max():.0f} dtk).")
    n = len(tf)
    lines.append(f"<b>{(tf['congestion_level'] == 'MACET').mean() * 100:.1f}%</b> observasi berlevel MACET dan "
                 f"<b>{(tf['congestion_level'] == 'PADAT').mean() * 100:.1f}%</b> PADAT (dari {n:,} observasi).")
    cor = tf.groupby("corridor")["congestion_pct"].mean().sort_values(ascending=False)
    if len(cor) > 1:
        lines.append(f"Koridor dengan rata-rata congestion tertinggi: <b>{cor.index[0]}</b> ({cor.iloc[0]:.1f}%) "
                     f"vs terendah {cor.index[-1]} ({cor.iloc[-1]:.1f}%).")
    return lines


def page_overview(tf, inc):
    header("🚦 Executive Overview", "Ringkasan kondisi lalu lintas Surabaya. Congestion index = 1 − speed ratio. "
           "Waktu dalam WIB.", tf)
    n = len(tf)
    n_padat = int((tf["congestion_level"] == "PADAT").sum())
    n_macet = int((tf["congestion_level"] == "MACET").sum())
    kpi_row([
        ("Average Congestion", fmt(tf["congestion_pct"].mean(), 1, "%"), "rata-rata congestion index"),
        ("Average Speed", fmt(tf["current_speed"].mean(), 1, " km/j"),
         f"free-flow {fmt(tf['free_flow_speed'].mean(), 1, ' km/j')}"),
        ("Average Delay", fmt(tf["delay_seconds"].mean(), 0, " dtk"), f"≈ {fmt(tf['delay_seconds'].mean() / 60, 1, ' menit')}"),
        ("PADAT Observations", f"{n_padat:,}", f"{n_padat / n * 100:.1f}% dari {n:,}"),
        ("MACET Observations", f"{n_macet:,}", f"{n_macet / n * 100:.1f}% dari {n:,}"),
        ("Incident Count", f"{0 if inc is None else len(inc):,}", "periode terpilih"),
    ])
    st.markdown("**Insight otomatis (deskriptif):**")
    st.markdown('<div class="insight"><ul>' + "".join(f"<li>{l}</li>" for l in auto_insights(tf)) + "</ul></div>",
                unsafe_allow_html=True)
    st.write("")

    st.subheader("Traffic Condition Map")
    mode = st.radio("Tampilan peta", ["Rata-rata periode terpilih", "Snapshot terbaru"], horizontal=True)
    if mode.startswith("Rata"):
        m = agg_points(tf).rename(columns={"avg_congestion": "congestion_pct", "avg_delay": "delay_seconds",
                                           "avg_speed": "current_speed", "avg_free_flow": "free_flow_speed"})
    else:
        m = tf.loc[tf.groupby("point_id")["ts"].idxmax()]
    m = m.dropna(subset=["latitude", "longitude"]).copy()
    if m.empty:
        st.info("Koordinat tidak tersedia untuk titik terpilih.")
    else:
        m["size_val"] = m["delay_seconds"].clip(lower=0) + 10
        fig = make_map(
            m, "congestion_pct", "size_val",
            ["point_id", "location", "corridor", "current_speed", "free_flow_speed", "congestion_pct", "delay_seconds"],
            "<b>%{customdata[0]}</b> — %{customdata[1]}<br>Koridor: %{customdata[2]}"
            "<br>Kecepatan saat ini: %{customdata[3]:.1f} km/j<br>Free-flow: %{customdata[4]:.1f} km/j"
            "<br>Kemacetan: %{customdata[5]:.1f}%<br>Delay: %{customdata[6]:.0f} dtk<extra></extra>",
            color_continuous_scale=CONG_SCALE, range_color=(0, max(40, m["congestion_pct"].max())))
        fig.update_layout(coloraxis_colorbar=dict(title="Kemacetan (%)"))
        pchart(fig, "ov_map")
        st.caption("Warna = congestion index (%), ukuran lingkaran = delay (detik).")

    c1, c2 = st.columns(2)
    order = [f"{h:02d}:00" for h in range(24) if f"{h:02d}:00" in set(tf["hour_label"])]
    with c1:
        st.subheader("Congestion Trend by Hour")
        by = tf.groupby(["date", "hour_label"])["congestion_pct"].mean().reset_index()
        by["date"] = by["date"].astype(str)
        fig = px.line(by, x="hour_label", y="congestion_pct", color="date", markers=True,
                      category_orders={"hour_label": order},
                      labels={"hour_label": "Jam (WIB)", "congestion_pct": "Congestion (%)", "date": "Tanggal"})
        allh = tf.groupby("hour_label")["congestion_pct"].mean().reindex(order)
        fig.add_scatter(x=order, y=allh.values, mode="lines+markers", name="Rata-rata semua",
                        line=dict(color="#0f172a", dash="dash", width=3))
        pchart(fig, "ov_trend")
    with c2:
        st.subheader("Level Mix by Hour")
        mix = pd.crosstab(tf["hour_label"], tf["congestion_level"], normalize="index") * 100
        mix = mix.reindex(columns=[l for l in LEVELS if l in mix.columns]).reindex(order).reset_index()
        mix = mix.melt("hour_label", var_name="Level", value_name="Persen")
        fig = px.bar(mix, x="hour_label", y="Persen", color="Level", color_discrete_map=LEVEL_COLORS,
                     category_orders={"hour_label": order, "Level": LEVELS},
                     labels={"hour_label": "Jam (WIB)", "Persen": "% observasi"})
        fig.update_layout(barmode="stack")
        pchart(fig, "ov_mix")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Daily Congestion")
        dly = tf.groupby("date").agg(c=("congestion_pct", "mean"), jam=("hour", "nunique")).reset_index()
        dly["date"] = dly["date"].astype(str)
        dly["Cakupan"] = np.where(dly["jam"] < 20, "Parsial (<20 jam)", "Penuh")
        fig = px.bar(dly, x="date", y="c", color="Cakupan", text_auto=".1f", hover_data={"jam": True},
                     color_discrete_map={"Penuh": "#2563eb", "Parsial (<20 jam)": "#94a3b8"},
                     labels={"date": "Tanggal", "c": "Congestion rata-rata (%)", "jam": "Jam teramati"})
        pchart(fig, "ov_daily")
        st.caption("Hari parsial memiliki cakupan jam yang tidak lengkap sehingga rata-ratanya tidak sebanding.")
    with c4:
        st.subheader("Average Congestion by Corridor")
        cor = tf.groupby("corridor")["congestion_pct"].mean().reset_index().sort_values("congestion_pct")
        fig = px.bar(cor, x="congestion_pct", y="corridor", orientation="h", text_auto=".1f",
                     color="congestion_pct", color_continuous_scale=CONG_SCALE,
                     labels={"congestion_pct": "Congestion (%)", "corridor": ""})
        fig.update_coloraxes(showscale=False)
        pchart(fig, "ov_cor")

    st.subheader("Average Congestion by Monitoring Point")
    pt = tf.groupby("point_label")["congestion_pct"].mean().reset_index().sort_values("congestion_pct")
    fig = px.bar(pt, x="congestion_pct", y="point_label", orientation="h", text_auto=".2f",
                 color="congestion_pct", color_continuous_scale=CONG_SCALE,
                 labels={"congestion_pct": "Congestion (%)", "point_label": ""})
    fig.update_coloraxes(showscale=False)
    pchart(fig, "ov_pt")
    spread_note(agg_points(tf))


# ----------------------------------------------------------------------------
# PAGE 2 — TRAFFIC & HOTSPOT
# ----------------------------------------------------------------------------
def page_hotspot(tf, rg, f):
    header("🔥 Traffic & Hotspot", "Pola kemacetan menurut waktu dan lokasi.", tf)
    order = [f"{h:02d}:00" for h in range(24) if f"{h:02d}:00" in set(tf["hour_label"])]

    st.subheader("Congestion Heatmap (jam × titik monitoring)")
    piv = tf.pivot_table(index="point_label", columns="hour_label", values="congestion_index", aggfunc="mean")
    piv = piv.reindex(columns=order)
    piv = piv.loc[piv.mean(axis=1).sort_values(ascending=False).index]
    fig = px.imshow(piv, aspect="auto", color_continuous_scale=CONG_SCALE, zmin=0,
                    labels=dict(x="Jam (WIB)", y="Titik", color="Congestion index"))
    fig.update_xaxes(type="category")
    pchart(fig, "hs_heat")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Heatmap Tanggal × Jam (seluruh titik)")
        pv = tf.pivot_table(index=tf["date"].astype(str), columns="hour_label", values="congestion_pct",
                            aggfunc="mean").reindex(columns=order)
        fig = px.imshow(pv, aspect="auto", color_continuous_scale=CONG_SCALE, zmin=0,
                        labels=dict(x="Jam (WIB)", y="Tanggal", color="Congestion (%)"))
        fig.update_xaxes(type="category")
        pchart(fig, "hs_dateheat")
    with c2:
        st.subheader("Distribusi Congestion per Jam (titik-jam)")
        hp = hourly_points(tf, f["min_s"])
        if hp.empty:
            st.info("Tidak ada titik-jam yang memenuhi minimum sampel.")
        else:
            fig = px.box(hp, x="hour_label", y="congestion_pct", category_orders={"hour_label": order},
                         labels={"hour_label": "Jam (WIB)", "congestion_pct": "Congestion (%)"})
            pchart(fig, "hs_box")

    st.subheader("Timeline 10 Menit (grid reguler)")
    if rg is None or rg.empty:
        st.info("traffic_flow_regular tidak tersedia / kosong pada filter ini.")
    else:
        tl = rg.groupby(["ts", "corridor"])["congestion_pct"].mean().reset_index()
        fig = px.line(tl, x="ts", y="congestion_pct", color="corridor",
                      labels={"ts": "Waktu (WIB)", "congestion_pct": "Congestion (%)", "corridor": "Koridor"})
        pchart(fig, "hs_regular")
        gap = rg["is_gap"].mean() * 100 if "is_gap" in rg.columns else np.nan
        st.caption(f"Garis terputus = gap data (tidak ada observasi). Gap pada filter ini: {fmt(gap, 1, '%')} dari slot 10 menit.")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Current vs Free-Flow Speed")
        opts = ["Semua titik (rata-rata)"] + sorted(tf["point_label"].unique())
        sel = st.selectbox("Titik", opts)
        d = tf if sel == opts[0] else tf[tf["point_label"] == sel]
        s = d.groupby("hour_ts")[["current_speed", "free_flow_speed"]].mean().reset_index()
        fig = go.Figure()
        fig.add_scatter(x=s["hour_ts"], y=s["current_speed"], mode="lines", name="Current speed")
        fig.add_scatter(x=s["hour_ts"], y=s["free_flow_speed"], mode="lines", name="Free-flow speed", line=dict(dash="dash"))
        fig.update_xaxes(title="Waktu (WIB)")
        fig.update_yaxes(title="km/jam")
        pchart(fig, "hs_speed")
    with c4:
        st.subheader("Average Delay by Hour")
        dh = tf.groupby("hour_label")["delay_seconds"].mean().reindex(order).reset_index()
        fig = px.bar(dh, x="hour_label", y="delay_seconds", text_auto=".0f",
                     labels={"hour_label": "Jam (WIB)", "delay_seconds": "Delay rata-rata (dtk)"})
        pchart(fig, "hs_delayhour")

    c5, c6 = st.columns(2)
    with c5:
        st.subheader("Average Delay by Location")
        dl = tf.groupby("point_label")["delay_seconds"].mean().reset_index().sort_values("delay_seconds")
        fig = px.bar(dl, x="delay_seconds", y="point_label", orientation="h", text_auto=".1f",
                     labels={"delay_seconds": "Delay rata-rata (detik)", "point_label": ""})
        pchart(fig, "hs_delay")
    with c6:
        st.subheader("Speed Ratio Distribution")
        fig = px.histogram(tf, x="speed_ratio", nbins=30, color="congestion_level", color_discrete_map=LEVEL_COLORS,
                           category_orders={"congestion_level": LEVELS},
                           labels={"speed_ratio": "Speed ratio (current / free-flow)", "congestion_level": "Level"})
        fig.update_layout(yaxis_title="Jumlah observasi", bargap=0.03)
        pchart(fig, "hs_hist")

    st.subheader("Hotspot Summary")
    h = agg_points(tf).sort_values("avg_congestion", ascending=False)
    peak = (tf.groupby(["point_id", "hour_label"])["congestion_pct"].mean().reset_index()
            .sort_values("congestion_pct", ascending=False).drop_duplicates("point_id")[["point_id", "hour_label"]])
    h = h.merge(peak, on="point_id", how="left")
    h = h[["point_id", "location", "corridor", "avg_congestion", "max_congestion", "avg_delay", "avg_speed",
           "pct_macet", "hour_label", "observations"]]
    h.columns = ["point_id", "Lokasi", "Koridor", "Avg congestion (%)", "Max congestion (%)", "Avg delay (dtk)",
                 "Avg speed (km/j)", "% observasi MACET", "Jam puncak (WIB)", "Observasi"]
    show_df(h.round(2))
    spread_note(agg_points(tf))


# ----------------------------------------------------------------------------
# PAGE 3 — INCIDENTS
# ----------------------------------------------------------------------------
def page_incidents(inc, tf):
    header("⚠️ Traffic Incidents", "Incident dari traffic_incidents (dipetakan ke titik monitoring terdekat).")
    if inc is None:
        st.error("File traffic_incidents(.csv / _<timestamp>.csv) tidak ditemukan.")
        return
    if inc.empty:
        st.warning("Tidak ada incident pada filter terpilih.")
        return
    kpi_row([
        ("Total Incident", f"{len(inc):,}", "periode terpilih"),
        ("Severity Berat", f"{(inc['magnitude_label'] == 'Berat').mean() * 100:.0f}%", "dari seluruh incident"),
        ("Total Panjang Terdampak", fmt(inc["length_m"].sum() / 1000, 1, " km"), "jumlah length_m"),
        ("Rata-rata Delay", fmt(inc["delay_seconds"].mean(), 0, " dtk"), "incident dengan delay terisi"),
    ])

    def bar(col, title, order=None, color_map=None, key=None):
        c = inc[col].fillna("(kosong)").value_counts().reset_index()
        c.columns = [col, "jumlah"]
        fig = px.bar(c, x=col, y="jumlah", text_auto=True, title=title, color=col if color_map else None,
                     color_discrete_map=color_map, category_orders={col: order} if order else None,
                     labels={col: "", "jumlah": "Jumlah incident"})
        fig.update_layout(showlegend=False)
        pchart(fig, key)

    c1, c2, c3 = st.columns(3)
    with c1:
        bar("category_label", "Kategori", key="inc_cat")
    with c2:
        bar("magnitude_label", "Severity (magnitude)", MAG_ORDER, MAG_COLORS, "inc_mag")
    with c3:
        bar("description", "Deskripsi", key="inc_desc")

    c4, c5 = st.columns(2)
    with c4:
        st.subheader("Incident per Jam Pertama Terlihat (WIB)")
        hr = inc["first_hour"].value_counts().reindex(range(24), fill_value=0).reset_index()
        hr.columns = ["jam", "jumlah"]
        fig = px.bar(hr, x="jam", y="jumlah", labels={"jam": "Jam (WIB)", "jumlah": "Jumlah incident"})
        pchart(fig, "inc_hour")
    with c5:
        st.subheader("Incident per Titik Monitoring Terdekat")
        npnt = inc["nearest_point"].value_counts().reset_index()
        npnt.columns = ["point_id", "jumlah"]
        fig = px.bar(npnt, x="point_id", y="jumlah", text_auto=True, labels={"point_id": "Titik", "jumlah": "Jumlah"})
        pchart(fig, "inc_point")

    st.subheader("Affected Length vs Delay")
    sc = inc.dropna(subset=["length_m", "delay_seconds"])
    fig = px.scatter(sc, x="length_m", y="delay_seconds", color="magnitude_label", color_discrete_map=MAG_COLORS,
                     category_orders={"magnitude_label": MAG_ORDER}, hover_data=["description", "road"],
                     labels={"length_m": "Panjang terdampak (m)", "delay_seconds": "Delay (detik)",
                             "magnitude_label": "Severity"})
    pchart(fig, "inc_scatter")
    st.caption("Pola deskriptif; hubungan panjang antrean–delay tidak dibaca sebagai sebab-akibat.")

    st.subheader("Incident Hotspot Map")
    mm = inc.dropna(subset=["latitude", "longitude"]).copy()
    mm["size_val"] = mm["delay_seconds"].fillna(0).clip(lower=0) + 20
    mm["delay_txt"] = mm["delay_seconds"].fillna(-1)
    fig = make_map(
        mm, "magnitude_label", "size_val", ["category_label", "description", "road", "length_m", "delay_txt"],
        "<b>%{customdata[0]}</b> — %{customdata[1]}<br>%{customdata[2]}"
        "<br>Panjang: %{customdata[3]:.0f} m<br>Delay: %{customdata[4]:.0f} dtk<extra></extra>",
        color_discrete_map=MAG_COLORS, category_orders={"magnitude_label": MAG_ORDER})
    pchart(fig, "inc_map")

    st.subheader("Incident Detail")
    t = inc[["category_label", "magnitude_label", "description", "road", "length_m", "delay_seconds", "start_time",
             "end_time", "first_seen_at", "last_seen_at", "nearest_point"]].copy()
    t = t.sort_values("delay_seconds", ascending=False, na_position="last")
    t.columns = ["Kategori", "Severity", "Deskripsi", "Ruas", "Panjang (m)", "Delay (dtk)", "Mulai", "Selesai",
                 "Pertama terlihat", "Terakhir terlihat", "Titik terdekat"]
    t[["Panjang (m)", "Delay (dtk)"]] = t[["Panjang (m)", "Delay (dtk)"]].round(1)
    show_df(t)


# ----------------------------------------------------------------------------
# PAGE 4 — ENVIRONMENT
# ----------------------------------------------------------------------------
def env_city_frame(src, tf, data, f):
    """Frame per jam (rata-rata titik terfilter) + variabel cuaca/udara."""
    if src.startswith("mart"):
        mt = data.get("mart_traffic_features")
        if mt is None:
            return None
        mt = apply_point_filters(mt, f)
        mt = mt[mt["samples"] >= f["min_s"]].copy()
        mt["congestion_pct"] = mt["avg_congestion"] * 100
        mt["delay"] = mt["avg_delay_seconds"]
        mt["speed"] = mt["avg_speed"]
        cols = ["congestion_pct", "delay", "speed"] + [c for c in ENV_LABELS if c in mt.columns] + \
               [c for c in ["precipitation", "rain"] if c in mt.columns]
        return mt.groupby("hour_ts")[cols].mean().reset_index()
    hp = hourly_points(tf, f["min_s"])
    if hp.empty:
        return hp
    ch = hp.groupby("hour_ts").agg(congestion_pct=("congestion_pct", "mean"), delay=("delay", "mean"),
                                   speed=("speed", "mean")).reset_index()
    wx, aq = data.get("weather_hourly"), data.get("air_quality_hourly")
    if wx is not None:
        ch = ch.merge(wx[~wx["is_forecast"]][["hour_ts", "temperature", "relative_humidity", "precipitation", "rain",
                                              "wind_speed"]], on="hour_ts", how="left")
    if aq is not None:
        ch = ch.merge(aq[~aq["is_forecast"]][["hour_ts", "pm2_5", "pm10", "carbon_monoxide", "nitrogen_dioxide",
                                              "us_aqi"]], on="hour_ts", how="left")
    return ch


def corr_table(d, cols):
    d = d.copy()
    d["hod"] = d["hour_ts"].dt.hour
    rows = []
    for v in cols:
        x = d[[v, "congestion_pct", "hod"]].dropna()
        if len(x) < 8 or x[v].nunique() < 2:
            continue
        xr = x[v] - x.groupby("hod")[v].transform("mean")
        yr = x["congestion_pct"] - x.groupby("hod")["congestion_pct"].transform("mean")
        rr = xr.corr(yr) if xr.std() > 0 and yr.std() > 0 else np.nan
        rows.append({"Variabel": ENV_LABELS[v], "key": v, "n (jam)": len(x),
                     "Pearson r": x[v].corr(x["congestion_pct"]),
                     "Spearman ρ": x[v].corr(x["congestion_pct"], method="spearman"),
                     "r setelah pola jam dihapus": rr})
    return pd.DataFrame(rows)


def scatter_trend(d, x, key):
    d = d[[x, "congestion_pct", "hour_ts"]].dropna()
    if len(d) < 5:
        st.info(f"Jam yang beririsan terlalu sedikit (n={len(d)}).")
        return
    d["Jam (WIB)"] = d["hour_ts"].dt.hour
    fig = px.scatter(d, x=x, y="congestion_pct", color="Jam (WIB)", color_continuous_scale="Turbo",
                     hover_data={"hour_ts": True},
                     labels={x: ENV_LABELS[x], "congestion_pct": "Congestion rata-rata (%)"})
    if d[x].nunique() > 1:
        m, b = np.polyfit(d[x], d["congestion_pct"], 1)
        xs = np.linspace(d[x].min(), d[x].max(), 50)
        fig.add_scatter(x=xs, y=m * xs + b, mode="lines", name="Garis tren (OLS)", line=dict(dash="dash", color="#0f172a"))
    pchart(fig, key)
    st.caption(f"n = {len(d)} jam · Pearson r = {fmt(d[x].corr(d['congestion_pct']), 2)} · Spearman ρ = "
               f"{fmt(d[x].corr(d['congestion_pct'], method='spearman'), 2)} · warna = jam (WIB). Hubungan deskriptif, bukan kausal.")


def page_environment(tf, data, f):
    header("🌦️ Environment", "Hubungan deskriptif traffic vs cuaca/kualitas udara pada level jam. "
           "Korelasi tidak menunjukkan sebab-akibat.", tf)
    src = st.radio("Sumber data traffic untuk analisis lingkungan",
                   ["traffic_flow (mengikuti semua filter)", "mart_traffic_features (filter tanggal/koridor/titik)"],
                   horizontal=True)
    d = env_city_frame(src, tf, data, f)
    if d is None or d.empty:
        st.warning("Tidak ada data per jam yang memenuhi filter / minimum sampel.")
        return
    avail = [c for c in ENV_LABELS if c in d.columns]
    st.info(f"{len(d)} jam beririsan. Weather/AQ yang dipasangkan hanya data aktual (is_forecast = False)"
            + ("; mart tidak menandai aktual/forecast." if src.startswith("mart") else "."))

    if {"rain", "precipitation"} <= set(d.columns):
        w = d.dropna(subset=["rain", "precipitation"])
        if len(w) and w["rain"].sum() == 0 and w["precipitation"].sum() == 0:
            st.warning("rain = 0 dan precipitation = 0 pada seluruh jam yang beririsan dengan traffic. Dataset belum memiliki "
                       "variasi hujan, sehingga congestion saat hujan vs tidak hujan belum bisa dibandingkan.")
    st.caption("Catatan: traffic dan polusi sama-sama mengikuti pola jam dalam sehari. Tabel di bawah menampilkan "
               "korelasi mentah dan korelasi setelah pola rata-rata per jam dihapus.")

    ct = corr_table(d, avail)
    if not ct.empty:
        st.subheader("Ringkasan Korelasi (Congestion vs variabel lingkungan)")
        show_df(ct.drop(columns="key").round(3))
        mlt = ct.melt("Variabel", ["Pearson r", "r setelah pola jam dihapus"], var_name="Jenis", value_name="r")
        fig = px.bar(mlt, x="Variabel", y="r", color="Jenis", barmode="group", range_y=[-1, 1],
                     labels={"r": "Koefisien korelasi"})
        pchart(fig, "env_corr")
        st.caption("Dengan n jam yang kecil, tiap jam-dalam-sehari hanya punya beberapa pengamatan sehingga korelasi "
                   "residual tidak stabil — baca sebagai indikasi awal.")

    tabs = st.tabs(["Temperature", "PM2.5", "NO₂", "Indikator lain", "Pola per Jam", "Tren Weather & AQ"])
    with tabs[0]:
        scatter_trend(d, "temperature", "env_t") if "temperature" in d.columns else st.info("Data weather tidak tersedia.")
    with tabs[1]:
        scatter_trend(d, "pm2_5", "env_pm25") if "pm2_5" in d.columns else st.info("Data air quality tidak tersedia.")
    with tabs[2]:
        scatter_trend(d, "nitrogen_dioxide", "env_no2") if "nitrogen_dioxide" in d.columns else st.info("Data air quality tidak tersedia.")
    with tabs[3]:
        others = [c for c in ["pm10", "carbon_monoxide", "us_aqi", "relative_humidity", "wind_speed"] if c in d.columns]
        if others:
            k = st.selectbox("Variabel", others, format_func=lambda x: ENV_LABELS[x])
            scatter_trend(d, k, "env_other")
    with tabs[4]:
        if avail:
            k = st.selectbox("Bandingkan congestion dengan", avail, format_func=lambda x: ENV_LABELS[x], key="env_prof")
            dd = d.assign(hod=d["hour_ts"].dt.hour).groupby("hod")[["congestion_pct", k]].mean().reset_index()
            fig = go.Figure()
            fig.add_bar(x=dd["hod"], y=dd["congestion_pct"], name="Congestion (%)", marker_color="#93c5fd")
            fig.add_scatter(x=dd["hod"], y=dd[k], name=ENV_LABELS[k], yaxis="y2", mode="lines+markers",
                            line=dict(color="#ef4444"))
            fig.update_layout(xaxis_title="Jam (WIB)", yaxis_title="Congestion (%)",
                              yaxis2=dict(title=ENV_LABELS[k], overlaying="y", side="right"),
                              legend=dict(orientation="h", y=1.12))
            pchart(fig, "env_hod")
    with tabs[5]:
        aq, wx = data.get("air_quality_hourly"), data.get("weather_hourly")
        if aq is not None:
            var = st.selectbox("Polutan", ["pm2_5", "pm10", "nitrogen_dioxide", "carbon_monoxide", "us_aqi"],
                               format_func=lambda x: ENV_LABELS[x])
            a = aq.sort_values("hour_ts").assign(Tipe=lambda x: np.where(x["is_forecast"], "Forecast", "Aktual"))
            fig = px.line(a, x="hour_ts", y=var, color="Tipe", color_discrete_map={"Aktual": "#2563eb", "Forecast": "#f59e0b"},
                          labels={"hour_ts": "Waktu (WIB)", var: ENV_LABELS[var]})
            pchart(fig, "env_aq")
        if wx is not None:
            w = wx.sort_values("hour_ts").assign(Tipe=lambda x: np.where(x["is_forecast"], "Forecast", "Aktual"))
            c1, c2 = st.columns(2)
            with c1:
                fig = px.line(w, x="hour_ts", y="temperature", color="Tipe",
                              color_discrete_map={"Aktual": "#2563eb", "Forecast": "#f59e0b"},
                              labels={"hour_ts": "Waktu (WIB)", "temperature": "Temperature (°C)"})
                pchart(fig, "env_wx")
            with c2:
                fig = px.bar(w, x="hour_ts", y="precipitation", color="Tipe",
                             color_discrete_map={"Aktual": "#2563eb", "Forecast": "#f59e0b"},
                             labels={"hour_ts": "Waktu (WIB)", "precipitation": "Presipitasi (mm)"})
                pchart(fig, "env_rain")


# ----------------------------------------------------------------------------
# PAGE 5 — FORECAST & MODEL CHECK
# ----------------------------------------------------------------------------
def page_forecast(tf_base, data, f):
    header("🔮 Forecast & Model Check", "Evaluasi traffic_forecast terhadap traffic aktual per jam, dan prediksi jam ke depan.",
           tf_base)
    fc = data.get("traffic_forecast")
    if fc is None:
        st.error("File traffic_forecast(.csv) tidak ditemukan.")
        return
    fcf = apply_point_filters(fc, f)
    hp = hourly_points(tf_base, f["min_s"])
    if fcf.empty or hp.empty:
        st.warning("Tidak ada forecast/aktual pada filter ini.")
        return
    ev = fcf.merge(hp[["point_id", "hour_ts", "congestion_pct", "samples"]], on=["point_id", "hour_ts"])
    st.caption("Level aktual per jam ditentukan dari rata-rata congestion jam tersebut dengan ambang: "
               "LANCAR ≤ 20% < PADAT ≤ 50% < MACET (diturunkan dari data).")
    if ev.empty:
        st.info("Belum ada jam yang beririsan antara forecast dan aktual.")
    else:
        ev["error"] = ev["predicted_pct"] - ev["congestion_pct"]
        ev["abs_error"] = ev["error"].abs()
        ev["actual_level"] = level_from_pct(ev["congestion_pct"])
        ev["hod"] = ev["hour_ts"].dt.hour
        acc = (ev["actual_level"] == ev["predicted_level"]).mean() * 100
        kpi_row([
            ("Titik-jam Dievaluasi", f"{len(ev):,}", f"{ev['model_version'].nunique()} versi model"),
            ("MAE", fmt(ev["abs_error"].mean(), 1, " pp"), "rata-rata |prediksi − aktual|"),
            ("RMSE", fmt(np.sqrt((ev["error"] ** 2).mean()), 1, " pp"), "poin persentase"),
            ("Bias", fmt(ev["error"].mean(), 1, " pp"), "positif = cenderung over-predict"),
            ("Akurasi Level", fmt(acc, 0, "%"), "LANCAR / PADAT / MACET"),
        ])
        st.subheader("Aktual vs Prediksi (rata-rata titik terfilter)")
        fig = go.Figure()
        act = ev.groupby("hour_ts")["congestion_pct"].mean().reset_index()
        fig.add_scatter(x=act["hour_ts"], y=act["congestion_pct"], mode="lines", name="Aktual",
                        line=dict(color="#0f172a", width=3))
        for i, (ver, g) in enumerate(ev.groupby("model_version")):
            p = g.groupby("hour_ts")["predicted_pct"].mean().reset_index()
            fig.add_scatter(x=p["hour_ts"], y=p["predicted_pct"], mode="lines", name=f"Prediksi {ver}",
                            line=dict(color=COLORWAY[(i + 1) % len(COLORWAY)], dash="dot"))
        fig.update_layout(xaxis_title="Waktu (WIB)", yaxis_title="Congestion (%)", legend=dict(orientation="h", y=1.15))
        pchart(fig, "fc_line")

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("MAE per Versi Model")
            mv = ev.groupby("model_version").agg(MAE=("abs_error", "mean"), n=("abs_error", "size")).reset_index()
            fig = px.bar(mv, x="model_version", y="MAE", text_auto=".1f", hover_data={"n": True},
                         labels={"model_version": "Versi model", "MAE": "MAE (pp)"})
            pchart(fig, "fc_ver")
            st.caption("Tiap versi mencakup rentang waktu berbeda, jadi perbedaan MAE juga dipengaruhi periode evaluasi.")
        with c2:
            st.subheader("MAE vs Horizon Prediksi")
            ev["Horizon"] = pd.cut(ev["horizon_h"], [0, 3, 6, 12, 18, 24.01], labels=["0–3 j", "3–6 j", "6–12 j", "12–18 j", "18–24 j"])
            hz = ev.groupby("Horizon", observed=True).agg(MAE=("abs_error", "mean"), n=("abs_error", "size")).reset_index()
            fig = px.bar(hz, x="Horizon", y="MAE", text_auto=".1f", hover_data={"n": True}, labels={"MAE": "MAE (pp)"})
            pchart(fig, "fc_hor")

        c3, c4 = st.columns(2)
        with c3:
            st.subheader("MAE per Jam dalam Sehari (WIB)")
            hh = ev.groupby("hod")["abs_error"].mean().reset_index()
            fig = px.bar(hh, x="hod", y="abs_error", labels={"hod": "Jam (WIB)", "abs_error": "MAE (pp)"})
            pchart(fig, "fc_hod")
        with c4:
            st.subheader("Prediksi vs Aktual (titik-jam)")
            fig = px.scatter(ev, x="congestion_pct", y="predicted_pct", color="model_version", opacity=0.6,
                             labels={"congestion_pct": "Aktual (%)", "predicted_pct": "Prediksi (%)", "model_version": "Versi"})
            mx = float(max(ev["congestion_pct"].max(), ev["predicted_pct"].max()))
            fig.add_scatter(x=[0, mx], y=[0, mx], mode="lines", name="y = x", line=dict(dash="dash", color="#64748b"))
            pchart(fig, "fc_scatter")

        st.subheader("Confusion Matrix Level (aktual × prediksi)")
        cm = pd.crosstab(ev["actual_level"], ev["predicted_level"]).reindex(index=LEVELS, columns=LEVELS, fill_value=0)
        fig = px.imshow(cm, text_auto=True, color_continuous_scale="Blues",
                        labels=dict(x="Prediksi", y="Aktual", color="Jumlah"))
        pchart(fig, "fc_cm", height=380)

    st.subheader("Prediksi ke Depan (setelah data aktual terakhir)")
    last = hp["hour_ts"].max()
    fut = fcf[fcf["hour_ts"] > last].copy()
    if fut.empty:
        st.info(f"Tidak ada forecast setelah data aktual terakhir ({last:%d %b %H:%M} WIB).")
        return
    st.caption(f"Data aktual terakhir: {last:%d %b %Y %H:%M} WIB. Prediksi berasal dari model_version terbaru per titik-jam.")
    fut["jam"] = fut["hour_ts"].dt.strftime("%d %b %H:00")
    pv = fut.pivot_table(index="point_label", columns="jam", values="predicted_pct", aggfunc="mean")
    pv = pv.reindex(columns=fut.sort_values("hour_ts")["jam"].unique())
    fig = px.imshow(pv, aspect="auto", color_continuous_scale=CONG_SCALE, zmin=0,
                    labels=dict(x="Jam target (WIB)", y="Titik", color="Prediksi (%)"))
    fig.update_xaxes(type="category")
    pchart(fig, "fc_future_heat")
    c1, c2 = st.columns(2)
    with c1:
        cnt = fut[fut["predicted_level"] == "MACET"].groupby("corridor").size().reset_index(name="titik-jam MACET")
        if cnt.empty:
            st.info("Tidak ada titik-jam diprediksi MACET pada periode ke depan.")
        else:
            fig = px.bar(cnt, x="corridor", y="titik-jam MACET", text_auto=True, labels={"corridor": "Koridor"})
            pchart(fig, "fc_future_macet")
    with c2:
        t = fut.sort_values("predicted_pct", ascending=False).head(15)[
            ["point_id", "location", "corridor", "jam", "predicted_pct", "predicted_level", "model_version"]]
        t.columns = ["Point", "Lokasi", "Koridor", "Jam target (WIB)", "Prediksi (%)", "Level", "Versi"]
        show_df(t.round(1))


# ----------------------------------------------------------------------------
# PAGE 6 — CONGESTION REDUCTION STRATEGY
# ----------------------------------------------------------------------------
def minmax(s):
    r = s.max() - s.min()
    return (s - s.min()) / r if r > 0 else s * 0


def peak_table(tf):
    g = tf.groupby(["point_id", "hour"]).agg(c=("congestion_pct", "mean"), d=("delay_seconds", "mean")).reset_index()
    rows = []
    for pid, d in g.groupby("point_id"):
        d = d.sort_values("c", ascending=False)
        p1 = d.iloc[0]
        gap = (d["hour"] - p1["hour"]).abs()
        far = d[np.minimum(gap, 24 - gap) >= 4]
        p2 = far.iloc[0] if len(far) else None
        rows.append({"point_id": pid, "crit": f"{int(p1['hour']):02d}:00", "h_cong": p1["c"], "h_delay": p1["d"],
                     "second": f"{int(p2['hour']):02d}:00" if p2 is not None else "–",
                     "second_cong": p2["c"] if p2 is not None else np.nan})
    return pd.DataFrame(rows)


def page_strategy(tf, inc, mp):
    header("🎯 Congestion Reduction Strategy", "Target utama: menurunkan tingkat kemacetan sebesar 15%.", tf)

    st.subheader("Congestion × Delay Priority Matrix")
    a = agg_points(tf)
    fig = px.scatter(a, x="avg_congestion", y="avg_delay", size="observations", color="corridor", text="point_id",
                     size_max=26, hover_data={"location": True, "observations": True, "avg_congestion": ":.2f", "avg_delay": ":.1f"},
                     labels={"avg_congestion": "Average congestion (%)", "avg_delay": "Average delay (detik)"})
    fig.update_traces(textposition="top center")
    if len(a) > 1:
        fig.add_vline(x=a["avg_congestion"].median(), line_dash="dot", line_color="#94a3b8", annotation_text="median")
        fig.add_hline(y=a["avg_delay"].median(), line_dash="dot", line_color="#94a3b8")
    pchart(fig, "st_matrix")
    st.caption("Kanan-atas = congestion dan delay di atas median titik terfilter → kandidat prioritas.")
    spread_note(a)

    st.subheader("Where and When Should the Team Investigate?")
    t = a.merge(peak_table(tf), on="point_id", how="left")
    t["priority"] = (0.5 * minmax(t["avg_congestion"]) + 0.5 * minmax(t["avg_delay"])) * 100
    if inc is not None and len(inc):
        t["n_inc"] = [int((haversine_km(r.latitude, r.longitude, inc["latitude"], inc["longitude"]) <= 1).sum())
                      for r in t.itertuples()]
    else:
        t["n_inc"] = np.nan
    t = t.sort_values("priority", ascending=False)
    out = t[["point_id", "location", "corridor", "crit", "h_cong", "h_delay", "second", "second_cong", "avg_congestion",
             "avg_delay", "pct_macet", "priority", "n_inc"]]
    out.columns = ["Point", "Lokasi", "Koridor", "Critical hour (WIB)", "Congestion jam kritis (%)", "Delay jam kritis (dtk)",
                   "Puncak ke-2 (≥4 jam dari puncak 1)", "Congestion puncak ke-2 (%)", "Avg congestion (%)",
                   "Avg delay (dtk)", "% observasi MACET", "Priority score", "Incident ≤1 km"]
    show_df(out.round(1))
    st.caption("Critical hour = jam dengan rata-rata congestion tertinggi per titik. Priority score = rata-rata sama-bobot "
               "(50:50) congestion & delay yang dinormalisasi min–max (heuristik, bukan standar resmi).")

    st.subheader("Target −15% Monitoring")
    c1, c2 = st.columns([1, 2])
    with c1:
        baseline = st.number_input("Baseline congestion (%)", min_value=0.0, max_value=100.0, value=25.0, step=0.5,
                                   help="Rata-rata congestion index (×100) pada periode baseline yang disepakati.")
        confirmed = st.checkbox("Baseline sudah disepakati stakeholder", value=False)
        if not confirmed:
            st.warning("Nilai 25% hanyalah contoh/input sementara, bukan fakta. Ganti dengan baseline yang disepakati.")
    current = tf["congestion_pct"].mean()
    target = baseline * (1 - TARGET_REDUCTION)
    abs_red = baseline - current
    rel_red = abs_red / baseline if baseline > 0 else np.nan
    progress = rel_red / TARGET_REDUCTION if baseline > 0 else np.nan
    with c2:
        kpi_row([
            ("Baseline", fmt(baseline, 1, "%"), "input pengguna"),
            ("Current", fmt(current, 1, "%"), f"{tf['date'].min()} s/d {tf['date'].max()}"),
            ("Target (−15%)", fmt(target, 1, "%"), "baseline × 0,85"),
            ("Observed reduction", fmt(rel_red * 100, 1, "%"), f"{fmt(abs_red, 1)} poin persentase"),
            ("Progress ke target", fmt(progress * 100, 0, "%"), "reduction ÷ 15%"),
        ])
    if baseline > 0:
        st.progress(float(np.clip(progress, 0, 1)))
    if not confirmed:
        st.info("Status: INDIKATIF — baseline belum dikonfirmasi, sehingga target tidak dapat dinyatakan tercapai/tidak tercapai.")
    elif progress >= 1:
        st.success("Status: pada periode & filter terpilih, current ≤ target. Pastikan periode dan jam observasi sebanding dengan baseline.")
    else:
        st.warning(f"Status: belum mencapai target (progress {fmt(progress * 100, 0, '%')}).")

    ca, cb = st.columns(2)
    with ca:
        st.markdown("**Congestion harian vs baseline & target**")
        dly = tf.groupby("date").agg(c=("congestion_pct", "mean"), jam=("hour", "nunique")).reset_index()
        dly["date"] = dly["date"].astype(str)
        fig = px.bar(dly, x="date", y="c", text_auto=".1f", hover_data={"jam": True},
                     labels={"date": "Tanggal", "c": "Congestion (%)", "jam": "Jam teramati"})
        fig.add_hline(y=baseline, line_dash="dash", line_color="#64748b", annotation_text="Baseline")
        fig.add_hline(y=target, line_dash="dash", line_color="#22c55e", annotation_text="Target −15%")
        pchart(fig, "st_daily")
        if (dly["jam"] < 20).any():
            st.caption("Ada hari parsial (<20 jam teramati): rata-rata harian tidak sebanding dengan hari penuh.")
    with cb:
        st.markdown("**Profil jam vs garis target (acuan rata-rata)**")
        hh = tf.groupby("hour_label")["congestion_pct"].mean().reset_index()
        fig = px.bar(hh, x="hour_label", y="congestion_pct", labels={"hour_label": "Jam (WIB)", "congestion_pct": "Congestion (%)"})
        fig.add_hline(y=target, line_dash="dash", line_color="#22c55e", annotation_text="Target −15%")
        pchart(fig, "st_hourly")
        st.caption("Garis target adalah acuan untuk rata-rata keseluruhan; jam di atas garis adalah kandidat intervensi, "
                   "bukan indikator pelanggaran target.")
    if tf["hour"].nunique() < 12:
        st.warning("Current dihitung dari jam observasi yang terbatas; baseline harus memakai metrik, filter, dan jam yang sama.")


# ----------------------------------------------------------------------------
# PAGE 7 — DATA QUALITY
# ----------------------------------------------------------------------------
def page_quality(data, meta, ignored, f):
    st.title("🧪 Data Quality")
    cov = {"traffic_flow": ("ts", "point_id"), "traffic_flow_regular": ("ts", "point_id"),
           "traffic_hourly": ("hour_ts", "point_id"), "traffic_incidents": ("first_seen_at", None),
           "traffic_forecast": ("hour_ts", "point_id"), "mart_traffic_features": ("hour_ts", "point_id"),
           "weather_hourly": ("hour_ts", None), "air_quality_hourly": ("hour_ts", None),
           "monitoring_points": (None, "point_id")}
    rows = []
    for k in DATASETS:
        if k not in meta:
            rows.append({"Dataset": k, "File": "TIDAK DITEMUKAN", "Baris": None, "Kolom": None,
                         "Coverage awal (WIB)": "–", "Coverage akhir (WIB)": "–", "Titik monitoring": "–"})
            continue
        tcol, pcol = cov[k]
        df = data[k]
        rows.append({"Dataset": k, "File": ", ".join(meta[k]["files"]), "Baris": meta[k]["rows"], "Kolom": meta[k]["cols"],
                     "Coverage awal (WIB)": str(df[tcol].min()) if tcol else "–",
                     "Coverage akhir (WIB)": str(df[tcol].max()) if tcol else "–",
                     "Titik monitoring": str(df[pcol].nunique()) if pcol else "–"})
    show_df(pd.DataFrame(rows))
    if ignored:
        st.caption("File lain yang cocok prefix tetapi lebih lama dan diabaikan: "
                   + "; ".join(f"{k}: {', '.join(v)}" for k, v in ignored.items()))

    tf = data["traffic_flow"]
    st.subheader("Komposisi sumber traffic_flow")
    sc = tf.groupby("source").agg(Baris=("point_id", "size"), Awal=("ts", "min"), Akhir=("ts", "max"),
                                  Titik=("point_id", "nunique")).reset_index()
    show_df(sc.astype({"Awal": str, "Akhir": str}))
    if "simulator" in set(tf["source"]):
        
    st.subheader("Temuan otomatis")
    hrs = tf["hour"].nunique()
    st.write(f"- traffic_flow: **{len(tf):,}** observasi, **{tf['date'].nunique()}** tanggal (WIB), **{hrs}/24** jam-dalam-sehari "
             f"terwakili. Tidak ada kolom vehicle_count.")
    if tf["date"].nunique() < 7:
        st.warning("Cakupan kurang dari 7 hari: pola hari-dalam-pekan (weekday vs weekend) belum bisa dinilai.")

    if "traffic_hourly" in data:
        th = data["traffic_hourly"]
        raw_h = hourly_points(tf, 1)
        j = th.merge(raw_h[["point_id", "hour_ts", "congestion_pct", "samples"]], on=["point_id", "hour_ts"], how="outer",
                     indicator=True, suffixes=("_h", "_raw"))
        both = j[j["_merge"] == "both"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Baris traffic_hourly", f"{len(th):,}")
        c2.metric("Titik-jam di raw saja", int((j["_merge"] == "right_only").sum()))
        c3.metric("MAE hourly vs raw", fmt((both["avg_congestion"] * 100 - both["congestion_pct"]).abs().mean(), 2, " pp"))
        c4.metric("Baris samples < 10", int((th["samples"] < 10).sum()))
        st.caption("Validasi traffic_hourly terhadap agregasi dari traffic_flow mentah (sumber utama dashboard).")
    if "mart_traffic_features" in data and "traffic_hourly" in data:
        mj = data["mart_traffic_features"].merge(data["traffic_hourly"], on=["point_id", "hour_ts"], suffixes=("", "_t"))
        st.write(f"- mart_traffic_features: {len(data['mart_traffic_features']):,} baris; selisih maksimum avg_congestion vs "
                 f"traffic_hourly pada {len(mj):,} titik-jam yang cocok = "
                 f"{fmt((mj['avg_congestion'] - mj['avg_congestion_t']).abs().max(), 4)}.")

    if "traffic_flow_regular" in data:
        rg = data["traffic_flow_regular"]
        st.subheader("Kualitas grid reguler 10 menit")
        c1, c2, c3 = st.columns(3)
        c1.metric("Slot gap", f"{rg['is_gap'].mean() * 100:.1f}%")
        c2.metric("Slot terisi (filled)", f"{rg['is_filled'].mean() * 100:.1f}%")
        c3.metric("Median umur data (dtk)", fmt(rg["age_seconds"].median(), 0))
        g = rg.groupby("date").agg(gap=("is_gap", "sum"), filled=("is_filled", "sum")).reset_index()
        g["date"] = g["date"].astype(str)
        g = g.melt("date", var_name="Status", value_name="Slot")
        fig = px.bar(g, x="date", y="Slot", color="Status", barmode="group", labels={"date": "Tanggal (WIB)"})
        pchart(fig, "dq_gap")

    st.subheader("Sampel per titik-jam (traffic_flow terfilter sumber)")
    hs = hourly_points(tf, 1)
    fig = px.histogram(hs, x="samples", nbins=40, labels={"samples": "Sampel per titik-jam"})
    fig.update_layout(yaxis_title="Jumlah titik-jam")
    pchart(fig, "dq_samples")

    if "traffic_forecast" in data:
        fc = data["traffic_forecast"]
        st.subheader("Versi model forecast")
        v = fc.groupby("model_version").agg(Baris=("point_id", "size"), Target_awal=("hour_ts", "min"),
                                            Target_akhir=("hour_ts", "max"), Dibuat_awal=("created_ts", "min"),
                                            Dibuat_akhir=("created_ts", "max")).reset_index()
        show_df(v.astype({c: str for c in ["Target_awal", "Target_akhir", "Dibuat_awal", "Dibuat_akhir"]}))

    for k in ["weather_hourly", "air_quality_hourly"]:
        if k in data:
            d = data[k]
            a, fo = d[~d["is_forecast"]], d[d["is_forecast"]]
            st.write(f"- {k}: {len(a)} jam aktual ({a['hour_ts'].min()} → {a['hour_ts'].max()}) + {len(fo)} jam forecast "
                     f"({fo['hour_ts'].min()} → {fo['hour_ts'].max()}).")
    if "weather_hourly" in data:
        w = data["weather_hourly"]
        act = w[~w["is_forecast"]]
        if act[["rain", "precipitation"]].fillna(0).sum().sum() == 0:
            st.warning("Weather aktual: rain = 0 dan precipitation = 0 (tidak ada variasi hujan). Hujan hanya muncul pada jam forecast.")

    st.subheader("Keterbatasan")
    st.markdown(
        "1. **Tidak ada `vehicle_count`** — volume kendaraan tidak dapat dianalisis; dashboard memakai speed, congestion index, dan delay.\n"
        "2. **traffic_flow menggunakan data statis berbasis TomTom**; dashboard tidak melakukan pengambilan data TomTom secara realtime.\n"
        "3. **`traffic_hourly` / mart** adalah agregasi turunan; dashboard memakai agregasi dari traffic_flow mentah sebagai sumber utama dan memvalidasinya di atas.\n"
        "4. **Weather & air quality berisi actual + forecast**; hanya data aktual dipasangkan dengan traffic.\n"
        "5. **Korelasi ≠ kausalitas**; traffic dan polusi sama-sama mengikuti pola jam, dan n jam masih kecil.\n"
        "6. **Cakupan waktu pendek**; belum ada pola mingguan/musiman dan hari parsial dapat membiaskan rata-rata harian.\n"
        "7. **Target −15% membutuhkan baseline yang disepakati** (metrik, periode, dan jam yang sama dengan current)."
    )


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    files, ignored = {}, {}
    for k in DATASETS:
        ps = find_files(k)
        if not ps:
            continue
        chosen = ps if k in MULTI else ps[:1]
        files[k] = [(str(p), p.stat().st_mtime) for p in chosen]
        if k not in MULTI and len(ps) > 1:
            ignored[k] = [p.name for p in ps[1:]]
    missing = [k for k in ["monitoring_points", "traffic_flow"] if k not in files]
    if missing:
        st.error(f"File wajib tidak ditemukan: {', '.join(missing)}. Folder yang dicari: "
                 + ", ".join(str(d) for d in SEARCH_DIRS))
        st.stop()

    data, meta = load_all(files)
    tf_all = data["traffic_flow"]

    if st.get_option("theme.base") != "light":
        st.sidebar.warning("Tema light belum dipaksa. Jalankan dari folder project (ada .streamlit/config.toml) "
                           "atau pakai run_dashboard.ps1.")
    st.sidebar.markdown("## 🚦 Surabaya Traffic")
    page = st.sidebar.radio("Halaman", [
        "1. Executive Overview", "2. Traffic & Hotspot", "3. Traffic Incidents", "4. Environment",
        "5. Forecast & Model Check", "6. Congestion Reduction Strategy", "7. Data Quality"])
    st.sidebar.markdown("---")
    f = sidebar_filters(tf_all)

    if page.startswith("7"):
        page_quality(data, meta, ignored, f)
        return

    tf_base = apply_filters(tf_all, f, use_level=False)
    tf = tf_base[tf_base["congestion_level"].isin(f["lvl"])].copy()
    inc = filter_incidents(data.get("traffic_incidents"), f)
    if tf.empty and not page.startswith("3"):
        st.warning("Tidak ada data traffic untuk kombinasi filter ini. Ubah filter di sidebar.")
        return

    if page.startswith("1"):
        page_overview(tf, inc)
    elif page.startswith("2"):
        page_hotspot(tf, apply_point_filters(data.get("traffic_flow_regular"), f), f)
    elif page.startswith("3"):
        page_incidents(inc, tf)
    elif page.startswith("4"):
        page_environment(tf, data, f)
    elif page.startswith("5"):
        page_forecast(tf_base, data, f)
    elif page.startswith("6"):
        page_strategy(tf, inc, data["monitoring_points"])
    st.sidebar.caption(f"Data traffic: {tf_all['ts'].min():%d %b %Y} – {tf_all['ts'].max():%d %b %Y} (WIB)")


main()
