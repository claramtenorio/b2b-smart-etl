import logging
from typing import Dict, Any
import pandas as pd
from google import genai

from src.config import GEMINI_API_KEY, GEMINI_MODEL, QUALITY_REPORT_MD_PATH

logger = logging.getLogger(__name__)


def calculate_pipeline_kpis(
    raw_profile: Dict[str, Any],
    clean_profile: Dict[str, Any],
    det_stats: Dict[str, Any],
    df_clean: pd.DataFrame,
) -> Dict[str, Any]:
    """Calculates technical and business KPIs across the hybrid ETL pipeline"""
    health_delta = round(clean_profile["health_score"] - raw_profile["health_score"], 1)
    total_clean = len(df_clean)
    manual_review_count = int(df_clean["needs_manual_review"].sum()) if total_clean > 0 else 0
    auto_healed_rate = round(((total_clean - manual_review_count) / total_clean) * 100, 1) if total_clean > 0 else 0.0

    # Token efficiency: fields fixed deterministically vs semantic fields sent to AI
    det_fixes = det_stats.get("deterministic_fixes_applied", 0) + det_stats.get("locations_resolved_by_regex", 0)
    total_interventions = det_fixes + total_clean
    deterministic_offload_pct = round((det_fixes / total_interventions) * 100, 1) if total_interventions > 0 else 0.0

    return {
        "raw_health_score": raw_profile["health_score"],
        "clean_health_score": clean_profile["health_score"],
        "health_score_delta": health_delta,
        "duplicates_removed": det_stats.get("duplicates_removed", 0),
        "deterministic_fixes": det_fixes,
        "deterministic_offload_pct": deterministic_offload_pct,
        "auto_healed_rate": auto_healed_rate,
        "flagged_for_review": manual_review_count,
        "total_contract_volume_brl": round(float(df_clean["contract_value_brl"].sum()), 2),
    }


def generate_data_quality_report(
    kpis: Dict[str, Any],
    df_audit: pd.DataFrame,
    force_refresh: bool = False,
) -> str:
    """Generates an AI-authored Executive Data Quality Report in Markdown"""
    if QUALITY_REPORT_MD_PATH.exists() and not force_refresh:
        logger.info(f"Loading existing Data Quality Report from {QUALITY_REPORT_MD_PATH.name}")
        return QUALITY_REPORT_MD_PATH.read_text(encoding="utf-8")

    logger.info("Generating Executive Data Quality Report via Gemini...")
    client = genai.Client(api_key=GEMINI_API_KEY)

    audit_sample = df_audit[["partner_id", "raw_company_name", "clean_company_name", "standardized_category", "needs_manual_review", "audit_notes"]].to_dict(orient="records")

    prompt = f"""You are a Lead Data Engineer reporting on a B2B Partner Onboarding ETL batch.
Write a concise, high-impact Executive Data Quality Report in Markdown (in English) based on these exact pipeline metrics:
- Initial Data Health Score: {kpis['raw_health_score']}% -> Final Health Score: {kpis['clean_health_score']}% (+{kpis['health_score_delta']}% improvement)
- Exact Duplicates Removed: {kpis['duplicates_removed']}
- Deterministic Offload Rate (Pandas/Regex fixes before LLM): {kpis['deterministic_offload_pct']}% ({kpis['deterministic_fixes']} structural fixes)
- Auto-Healing Rate: {kpis['auto_healed_rate']}% ({kpis['flagged_for_review']} records flagged for manual compliance review)
- Total Sanitized Contract Volume: R$ {kpis['total_contract_volume_brl']:,.2f}

Audit Log Sample:
{audit_sample}

Structure the report into 3 exact sections using Markdown headers (###):
1. ### What Happened (Batch Health & Anomaly Overview)
2. ### Why It Happened (Root Causes in Partner Ingestion)
3. ### Actionable Governance Recommendations (Next Steps for Engineering & Operations)
Keep it factual, metric-driven, and concise."""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    report_md = response.text or "Report generation unavailable."
    QUALITY_REPORT_MD_PATH.write_text(report_md, encoding="utf-8")
    logger.info(f"Saved Data Quality Report to {QUALITY_REPORT_MD_PATH}")
    return report_md