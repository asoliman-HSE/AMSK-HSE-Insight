import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="HSE Dashboard", page_icon="🦺", layout="wide")


# ---------- Sample data (used until you upload your own file) ----------
@st.cache_data
def make_sample_data(n=300):
    rng = np.random.default_rng(42)
    dates = pd.to_datetime("2026-01-01") + pd.to_timedelta(rng.integers(0, 300, n), unit="D")
    return pd.DataFrame({
        "Date": dates,
        "Site": rng.choice(["Plant A", "Plant B", "Workshop", "Field Ops"], n),
        "Department": rng.choice(["Production", "Maintenance", "Logistics", "Quality"], n),
        "Incident Type": rng.choice(
            ["Near Miss", "First Aid", "Medical Treatment", "Lost Time", "Property Damage"],
            n, p=[0.45, 0.25, 0.12, 0.06, 0.12]),
        "Severity": rng.choice(["Low", "Medium", "High"], n, p=[0.6, 0.3, 0.1]),
        "Status": rng.choice(["Open", "Closed"], n, p=[0.3, 0.7]),
    }).sort_values("Date").reset_index(drop=True)


def load_file(uploaded):
    if uploaded.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded)
    return pd.read_excel(uploaded)


# ---------- Sidebar: upload ----------
st.sidebar.title("🦺 HSE Dashboard")
uploaded = st.sidebar.file_uploader("Upload Excel or CSV file", type=["xlsx", "xls", "csv"])

if uploaded:
    try:
        df = load_file(uploaded)
        st.sidebar.success(f"Loaded: {uploaded.name}")
    except Exception as e:
        st.error(f"Could not read the file: {e}")
        st.stop()
else:
    df = make_sample_data()
    st.sidebar.info("Showing sample data. Upload your own file to analyse it.")

df.columns = [str(c).strip() for c in df.columns]

# Try to detect date columns automatically
for col in df.columns:
    if not pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_datetime64_any_dtype(df[col]) and "date" in col.lower():
        df[col] = pd.to_datetime(df[col], errors="coerce")
date_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
cat_cols = [c for c in df.columns
            if not pd.api.types.is_numeric_dtype(df[c])
            and not pd.api.types.is_datetime64_any_dtype(df[c])
            and df[c].nunique() <= 50]

# ---------- Sidebar: column choices & filters ----------
st.sidebar.subheader("Settings")
date_col = st.sidebar.selectbox("Date column", ["(none)"] + date_cols,
                                index=1 if date_cols else 0)
default_group = next((i + 1 for i, c in enumerate(cat_cols) if "type" in c.lower()),
                     1 if cat_cols else 0)
group_col = st.sidebar.selectbox("Main category (e.g. Incident Type)", ["(none)"] + cat_cols,
                                 index=default_group)

st.sidebar.subheader("Filters")
filtered = df.copy()
if date_col != "(none)" and filtered[date_col].notna().any():
    dmin, dmax = filtered[date_col].min().date(), filtered[date_col].max().date()
    rng_sel = st.sidebar.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
    if isinstance(rng_sel, tuple) and len(rng_sel) == 2:
        filtered = filtered[filtered[date_col].dt.date.between(rng_sel[0], rng_sel[1])]

for col in cat_cols[:4]:
    options = sorted(filtered[col].dropna().unique().tolist())
    chosen = st.sidebar.multiselect(col, options)
    if chosen:
        filtered = filtered[filtered[col].isin(chosen)]

# ---------- Main page ----------
st.title("HSE Performance Dashboard")
st.caption("Upload your HSE records (incidents, near misses, inspections...) to see KPIs and trends.")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total records", f"{len(filtered):,}")
k2.metric("Columns", len(df.columns))
if group_col != "(none)" and len(filtered):
    top = filtered[group_col].value_counts()
    k3.metric(f"Most common {group_col}", str(top.index[0]))
    k4.metric("Categories", filtered[group_col].nunique())

st.divider()
c1, c2 = st.columns(2)

if date_col != "(none)" and len(filtered):
    monthly = (filtered.dropna(subset=[date_col])
               .assign(Month=lambda d: d[date_col].dt.to_period("M").dt.to_timestamp()))
    if group_col != "(none)":
        trend = monthly.groupby(["Month", group_col]).size().reset_index(name="Count")
        fig = px.bar(trend, x="Month", y="Count", color=group_col, title="Monthly trend")
    else:
        trend = monthly.groupby("Month").size().reset_index(name="Count")
        fig = px.line(trend, x="Month", y="Count", markers=True, title="Monthly trend")
    c1.plotly_chart(fig, use_container_width=True)
else:
    c1.info("Choose a date column in the sidebar to see the monthly trend.")

if group_col != "(none)" and len(filtered):
    counts = filtered[group_col].value_counts().reset_index()
    counts.columns = [group_col, "Count"]
    fig2 = px.bar(counts, x="Count", y=group_col, orientation="h",
                  title=f"Records by {group_col}")
    fig2.update_layout(yaxis={"categoryorder": "total ascending"})
    c2.plotly_chart(fig2, use_container_width=True)
else:
    c2.info("Choose a main category in the sidebar to see the breakdown.")

st.subheader("Data")
st.dataframe(filtered, use_container_width=True)
st.download_button("Download filtered data (CSV)",
                   filtered.to_csv(index=False).encode("utf-8"),
                   "hse_filtered.csv", "text/csv")
