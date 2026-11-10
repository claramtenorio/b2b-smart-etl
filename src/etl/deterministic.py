import logging
import re
from datetime import datetime
from typing import Tuple, Dict, Any
import pandas as pd
from src.config import VALID_BR_STATES

logger = logging.getLogger(__name__)


def clean_cnpj(raw_val: Any) -> Tuple[str, bool, str]:
    """Extracts digits and formats a 14-digit Brazilian CNPJ into the standard 'XX.XXX.XXX/XXXX-XX' pattern"""
    if pd.isna(raw_val) or not str(raw_val).strip():
        return "00.000.000/0000-00", False, "Missing CNPJ"

    digits = re.sub(r"\D", "", str(raw_val))
    if len(digits) != 14 or len(set(digits)) == 1:
        return digits or "INVALID", False, f"Invalid CNPJ length ({len(digits)} digits)"

    formatted = f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return formatted, True, "CNPJ standardized via Regex"


def parse_contract_value(raw_val: Any) -> Tuple[float, bool, str]:
    """Converts messy currency strings (e.g., 'R$ 45.000,00', '28.5 mil reais') into float."""
    if pd.isna(raw_val) or not str(raw_val).strip():
        return 0.0, True, "Missing contract value"

    text = str(raw_val).lower().strip()
    is_negative = "-" in text

    multiplier = 1.0
    if "mil" in text or "k" in text:
        multiplier = 1000.0

    num_str = re.sub(r"[^\d.,]", "", text)
    if not num_str:
        return 0.0, True, f"Unparseable currency: {raw_val}"

    if "," in num_str and "." in num_str:
        if num_str.rfind(",") > num_str.rfind("."):
            num_str = num_str.replace(".", "").replace(",", ".")
        else:
            num_str = num_str.replace(",", "")
    elif "," in num_str:
        num_str = num_str.replace(",", ".")

    try:
        val = float(num_str) * multiplier
        if is_negative:
            val = abs(val)
            return round(val, 2), True, "Negative contract value inverted to positive (flagged)"
        if val <= 0:
            return 0.0, True, "Zero contract value flagged for review"
        return round(val, 2), False, "Currency parsed deterministically"
    except ValueError:
        return 0.0, True, f"Failed numeric conversion: {raw_val}"


def standardize_date(raw_val: Any) -> Tuple[str, str]:
    """Normalizes heterogeneous date formats to ISO YYYY-MM-DD."""
    if pd.isna(raw_val) or not str(raw_val).strip():
        return "2026-01-01", "Missing date defaulted to 2026-01-01"

    text = str(raw_val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%Y-%m-%d"), "Date normalized to ISO"
        except ValueError:
            continue

    return "2026-01-01", f"Invalid date '{text}' replaced with fallback ISO date"


def clean_email(raw_val: Any) -> Tuple[str, str]:
    """Normalizes email casing and repairs common '_at_' typos."""
    if pd.isna(raw_val) or not str(raw_val).strip():
        return "missing@partner.b2b", "Missing email replaced with placeholder"

    email = str(raw_val).strip().lower().replace("_at_", "@")
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return email, "Email validated"
    return email, "Invalid email format flagged"


def try_deterministic_location(raw_loc: Any) -> Tuple[str, str, bool]:
    """Attempts to extract City and 2-letter State (UF) via Regex before calling AI."""
    if pd.isna(raw_loc) or not str(raw_loc).strip():
        return "Unknown", "NA", False

    text = str(raw_loc).strip()
    match = re.match(r"^([A-Za-zÀ-ÿ\s]+?)\s*[-/]\s*([A-Za-z]{2})$", text)
    if match:
        city = match.group(1).strip().title()
        uf = match.group(2).strip().upper()
        if uf in VALID_BR_STATES:
            return city, uf, True
    return text, "NA", False


def run_deterministic_cleaning(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Executes Layer 1 deterministic cleaning rules across the dataset."""
    initial_count = len(df_raw)
    df = df_raw.drop_duplicates(subset=["partner_id"], keep="first").copy()
    duplicates_removed = initial_count - len(df)

    records = []
    deterministic_fixes_count = duplicates_removed

    for _, row in df.iterrows():
        notes = []
        clean_tax, cnpj_ok, cnpj_note = clean_cnpj(row.get("tax_id_cnpj"))
        val_brl, val_anom, val_note = parse_contract_value(row.get("contract_value"))
        iso_date, date_note = standardize_date(row.get("onboarding_date"))
        email, email_note = clean_email(row.get("contact_email"))
        det_city, det_uf, loc_resolved = try_deterministic_location(row.get("raw_location"))

        for n in (cnpj_note, val_note, date_note, email_note):
            if "Missing" in n or "Invalid" in n or "inverted" in n or "normalized" in n:
                notes.append(n)
                deterministic_fixes_count += 1

        records.append({
            "partner_id": str(row.get("partner_id")).strip(),
            "raw_company_name": str(row.get("company_name") or "").strip(),
            "clean_cnpj": clean_tax,
            "is_cnpj_valid": cnpj_ok,
            "raw_service_description": str(row.get("service_description") or "").strip(),
            "contract_value_brl": val_brl,
            "is_value_anomalous": val_anom,
            "raw_location": str(row.get("raw_location") or "").strip(),
            "det_city": det_city,
            "det_state": det_uf,
            "is_location_resolved": loc_resolved,
            "onboarding_date_iso": iso_date,
            "contact_email": email,
            "deterministic_notes": "; ".join(notes) if notes else "Passed deterministic checks",
        })

    df_det = pd.DataFrame(records)
    stats = {
        "initial_rows": initial_count,
        "deduplicated_rows": len(df_det),
        "duplicates_removed": duplicates_removed,
        "deterministic_fixes_applied": deterministic_fixes_count,
        "locations_resolved_by_regex": int(df_det["is_location_resolved"].sum()),
    }
    logger.info(f"Deterministic ETL complete: {stats}")
    return df_det, stats