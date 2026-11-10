import re
from typing import Dict, Any
import pandas as pd
from src.config import VALID_BR_STATES


def profile_raw_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculates baseline Data Quality metrics on the raw incoming dataset"""
    total_rows = len(df)
    if total_rows == 0:
        return {"health_score": 0.0}

    duplicate_rows = int(df.duplicated(subset=["partner_id"]).sum())
    uniqueness_score = ((total_rows - duplicate_rows) / total_rows) * 100

    total_cells = total_rows * len(df.columns)
    null_cells = int(df.isna().sum().sum() + (df == "").sum().sum())
    completeness_score = ((total_cells - null_cells) / total_cells) * 100

    valid_cnpjs = df["tax_id_cnpj"].fillna("").apply(
        lambda x: bool(re.match(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$", str(x).strip()))
    ).sum()
    valid_numeric_values = df["contract_value"].fillna("").apply(
        lambda x: bool(re.match(r"^\d+(\.\d{1,2})?$", str(x).strip())) and float(str(x)) > 0
    ).sum()
    valid_dates = df["onboarding_date"].fillna("").apply(
        lambda x: bool(re.match(r"^\d{4}-\d{2}-\d{2}$", str(x).strip()))
    ).sum()

    validity_score = ((valid_cnpjs + valid_numeric_values + valid_dates) / (total_rows * 3)) * 100
    overall_health = round((uniqueness_score * 0.25) + (completeness_score * 0.35) + (validity_score * 0.40), 1)

    return {
        "stage": "raw_before_etl",
        "total_rows": total_rows,
        "duplicate_rows": duplicate_rows,
        "null_cells": null_cells,
        "uniqueness_score": round(uniqueness_score, 1),
        "completeness_score": round(completeness_score, 1),
        "validity_score": round(validity_score, 1),
        "health_score": overall_health,
    }


def profile_clean_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculates post-ETL Data Quality metrics on the sanitized dataset"""
    total_rows = len(df)
    if total_rows == 0:
        return {"health_score": 0.0}

    duplicate_rows = int(df.duplicated(subset=["partner_id"]).sum())
    uniqueness_score = ((total_rows - duplicate_rows) / total_rows) * 100

    total_cells = total_rows * len(df.columns)
    null_cells = int(df.isna().sum().sum())
    completeness_score = ((total_cells - null_cells) / total_cells) * 100

    valid_cnpjs = int(df["is_cnpj_valid"].sum())
    valid_values = int((~df["is_value_anomalous"]).sum())
    valid_states = int(df["state"].isin(VALID_BR_STATES).sum())

    validity_score = ((valid_cnpjs + valid_values + valid_states) / (total_rows * 3)) * 100
    overall_health = round((uniqueness_score * 0.25) + (completeness_score * 0.35) + (validity_score * 0.40), 1)

    return {
        "stage": "clean_after_etl",
        "total_rows": total_rows,
        "duplicate_rows": duplicate_rows,
        "null_cells": null_cells,
        "uniqueness_score": round(uniqueness_score, 1),
        "completeness_score": round(completeness_score, 1),
        "validity_score": round(validity_score, 1),
        "health_score": overall_health,
    }