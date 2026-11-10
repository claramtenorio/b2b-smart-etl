import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Environment variables from .env file
load_dotenv()

# Base project directories
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"

# Make sure data directories exist
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Paths for ETL artifacts
RAW_PARTNERS_PATH: Path = RAW_DATA_DIR / "dirty_b2b_partners.csv"
CLEAN_PARTNERS_CSV_PATH: Path = PROCESSED_DATA_DIR / "clean_b2b_partners.csv"
AUDIT_LOG_CSV_PATH: Path = PROCESSED_DATA_DIR / "audit_trail.csv"
SQLITE_DB_PATH: Path = PROCESSED_DATA_DIR / "b2b_catalog.db"
QUALITY_REPORT_MD_PATH: Path = PROCESSED_DATA_DIR / "data_quality_report.md"
AI_CACHE_PATH: Path = PROCESSED_DATA_DIR / "ai_enrichment_cache.csv"

# Gemini API configuration
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

# Target categories for AI standardization
OFFICIAL_B2B_CATEGORIES: List[str] = [
    "Cloud & IT Infrastructure",
    "Logistics & Last-Mile Delivery",
    "Payment Processing & Fintech",
    "Corporate Catering & Food Supplies",
    "Marketing & Customer Acquisition",
    "Legal, Compliance & Accounting",
    "Facilities & Maintenance",
    "Unclassified",
]

# Brazilian states
VALID_BR_STATES: List[str] = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]