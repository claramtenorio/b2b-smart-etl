import sys
from pathlib import Path

# Ensure project root is in sys.path when launched via `streamlit run src/app.py`
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import sqlite3
import pandas as pd
import streamlit as st

from src.config import (
    RAW_PARTNERS_PATH,
    CLEAN_PARTNERS_CSV_PATH,
    AUDIT_LOG_CSV_PATH,
    SQLITE_DB_PATH,
    QUALITY_REPORT_MD_PATH,
)
from src.etl.profiler import profile_raw_dataset, profile_clean_dataset
from src.etl.deterministic import run_deterministic_cleaning
from src.analytics.quality_report import calculate_pipeline_kpis

st.set_page_config(
    page_title="B2B Smart ETL & Data Quality Monitor",
    layout="wide",
)

st.title("B2B Partner Onboarding — Hybrid ETL & Data Quality Monitor")
st.caption("Layer 1: Deterministic Pandas/Regex Engine | Layer 2: Gemini 3 Flash Semantic Steward | Storage: SQLite & Pydantic Contracts")

if not CLEAN_PARTNERS_CSV_PATH.exists() or not RAW_PARTNERS_PATH.exists():
    st.warning("Processed data artifacts not found. Please run `python3 main.py` first.")
    st.stop()

df_raw = pd.read_csv(RAW_PARTNERS_PATH, dtype=str)
df_clean = pd.read_csv(CLEAN_PARTNERS_CSV_PATH)
df_audit = pd.read_csv(AUDIT_LOG_CSV_PATH)

raw_prof = profile_raw_dataset(df_raw)
clean_prof = profile_clean_dataset(df_clean)
_, det_stats = run_deterministic_cleaning(df_raw)
kpis = calculate_pipeline_kpis(raw_prof, clean_prof, det_stats, df_clean)

# Top KPI Cards
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Raw Health Score", f"{kpis['raw_health_score']}%")
col2.metric("Post-ETL Health Score", f"{kpis['clean_health_score']}%", f"+{kpis['health_score_delta']}%")
col3.metric("Deterministic Offload", f"{kpis['deterministic_offload_pct']}%", f"{kpis['deterministic_fixes']} regex fixes")
col4.metric("Auto-Healing Rate", f"{kpis['auto_healed_rate']}%", f"{kpis['flagged_for_review']} flagged")
col5.metric("Sanitized Volume (BRL)", f"R$ {kpis['total_contract_volume_brl']:,.2f}")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Executive AI Insights & Charts",
    "🔍 Before vs. After Audit Trail",
    "🗄️ Clean Production Catalog (SQLite)",
    "🧪 Raw Dirty Input (Kaggle)",
])

with tab1:
    left_col, right_col = st.columns([1.2, 1])
    with left_col:
        st.subheader("🤖 AI Executive Data Quality Report")
        if QUALITY_REPORT_MD_PATH.exists():
            st.markdown(QUALITY_REPORT_MD_PATH.read_text(encoding="utf-8"))
        else:
            st.info("Run `python3 main.py` to generate the executive report.")

    with right_col:
        st.subheader("📈 Data Quality Dimensions (Before vs. After)")
        dims_df = pd.DataFrame({
            "Dimension": ["Uniqueness", "Completeness", "Validity", "Overall Health"],
            "Before ETL (%)": [
                raw_prof["uniqueness_score"],
                raw_prof["completeness_score"],
                raw_prof["validity_score"],
                raw_prof["health_score"],
            ],
            "After Hybrid ETL (%)": [
                clean_prof["uniqueness_score"],
                clean_prof["completeness_score"],
                clean_prof["validity_score"],
                clean_prof["health_score"],
            ],
        }).set_index("Dimension")
        st.bar_chart(dims_df)

        st.subheader("🏷️ Sanitized B2B Spend by Category (BRL)")
        cat_spend = df_clean.groupby("standardized_category")["contract_value_brl"].sum().sort_values(ascending=True)
        st.bar_chart(cat_spend)

with tab2:
    st.subheader("🔍 Field-Level Transformation Audit Trail")
    filter_review = st.checkbox("Show only records flagged for manual compliance review", value=False)
    audit_view = df_audit[df_audit["needs_manual_review"]] if filter_review else df_audit
    st.dataframe(audit_view, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("🗄️ Production SQLite Table (`b2b_partners`)")
    selected_cat = st.multiselect(
        "Filter by Official B2B Category:",
        options=sorted(df_clean["standardized_category"].unique()),
        default=sorted(df_clean["standardized_category"].unique()),
    )
    filtered_clean = df_clean[df_clean["standardized_category"].isin(selected_cat)]
    st.dataframe(filtered_clean, use_container_width=True, hide_index=True)

    if SQLITE_DB_PATH.exists():
        with sqlite3.connect(SQLITE_DB_PATH) as conn:
            sql_check = pd.read_sql_query(
                "SELECT state, COUNT(*) as partners, ROUND(SUM(contract_value_brl), 2) as total_brl FROM b2b_partners GROUP BY state ORDER BY total_brl DESC",
                conn,
            )
        st.caption("Live SQL Aggregation from `b2b_catalog.db` (Partners & Contract Volume by State):")
        st.dataframe(sql_check, use_container_width=True, hide_index=True)

with tab4:
    st.subheader("🧪 Original Unsanitized Dataset (`dirty_b2b_partners.csv`)")
    st.dataframe(df_raw, use_container_width=True, hide_index=True)