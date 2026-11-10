import logging
import sqlite3
from typing import Dict, Tuple
import pandas as pd

from src.config import CLEAN_PARTNERS_CSV_PATH, AUDIT_LOG_CSV_PATH, SQLITE_DB_PATH
from src.etl.schemas import AIEnrichmentOutput, CleanPartnerRecord

logger = logging.getLogger(__name__)


def merge_and_load_pipeline(
    df_det: pd.DataFrame,
    ai_outputs: Dict[str, AIEnrichmentOutput],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Merges Layer 1 (Deterministic) and Layer 2 (AI) outputs, validates via Pydantic, and persists to SQLite/CSV"""
    clean_rows = []
    audit_rows = []

    for _, row in df_det.iterrows():
        pid = str(row["partner_id"])
        ai_data = ai_outputs.get(pid)

        if not ai_data:
            raise RuntimeError(f"Missing AI enrichment output for partner_id={pid}")

        # Prefer deterministic location if resolved by Regex; otherwise use Gemini's inference
        final_city = row["det_city"] if row["is_location_resolved"] else ai_data.inferred_city
        final_state = row["det_state"] if row["is_location_resolved"] else ai_data.inferred_state

        loc_method = "Deterministic Regex" if row["is_location_resolved"] else "Gemini AI Inference"
        needs_review = bool(
            (not row["is_cnpj_valid"])
            or row["is_value_anomalous"]
            or ai_data.has_semantic_anomaly
        )

        combined_notes = f"Det: {row['deterministic_notes']} | AI: {ai_data.anomaly_notes}"

        # Validate against strict Pydantic production schema
        validated_record = CleanPartnerRecord(
            partner_id=pid,
            clean_company_name=ai_data.clean_company_name,
            clean_cnpj=str(row["clean_cnpj"]),
            is_cnpj_valid=bool(row["is_cnpj_valid"]),
            standardized_category=ai_data.standardized_category,
            executive_service_summary=ai_data.executive_service_summary,
            contract_value_brl=float(row["contract_value_brl"]),
            is_value_anomalous=bool(row["is_value_anomalous"]),
            city=final_city,
            state=final_state,
            onboarding_date_iso=str(row["onboarding_date_iso"]),
            contact_email=str(row["contact_email"]),
            needs_manual_review=needs_review,
            resolution_method=f"Hybrid ({loc_method} + Gemini Taxonomy)",
            audit_notes=combined_notes,
        )
        clean_rows.append(validated_record.model_dump())

        # Record before-and-after transformation for Data Governance Audit Trail
        audit_rows.append({
            "partner_id": pid,
            "raw_company_name": row["raw_company_name"],
            "clean_company_name": validated_record.clean_company_name,
            "raw_location": row["raw_location"],
            "clean_location": f"{validated_record.city} - {validated_record.state}",
            "location_resolved_by": loc_method,
            "standardized_category": validated_record.standardized_category,
            "contract_value_brl": validated_record.contract_value_brl,
            "needs_manual_review": validated_record.needs_manual_review,
            "audit_notes": combined_notes,
        })

    df_clean = pd.DataFrame(clean_rows)
    df_audit = pd.DataFrame(audit_rows)

    # Save CSV artifacts
    df_clean.to_csv(CLEAN_PARTNERS_CSV_PATH, index=False)
    df_audit.to_csv(AUDIT_LOG_CSV_PATH, index=False)

    # Load into relational SQLite database (idempotent replace)
    with sqlite3.connect(SQLITE_DB_PATH) as conn:
        df_clean.to_sql("b2b_partners", conn, if_exists="replace", index=False)
        df_audit.to_sql("data_audit_trail", conn, if_exists="replace", index=False)

    logger.info(
        f"Loaded {len(df_clean)} validated records into SQLite ({SQLITE_DB_PATH.name}) and CSVs."
    )
    return df_clean, df_audit