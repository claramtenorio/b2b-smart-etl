import logging
from src.etl.extractor import extract_kaggle_marketplace_data
from src.etl.profiler import profile_raw_dataset, profile_clean_dataset
from src.etl.deterministic import run_deterministic_cleaning
from src.agents.cleaner_agent import DataStewardAgent
from src.etl.loader import merge_and_load_pipeline
from src.analytics.quality_report import calculate_pipeline_kpis, generate_data_quality_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=== Starting B2B Smart Hybrid ETL Pipeline ===")

    # Extract & Initial Data Profiling
    logger.info("[1/4] Extracting raw marketplace dataset and running baseline profiler...")
    df_raw = extract_kaggle_marketplace_data()
    raw_profile = profile_raw_dataset(df_raw)
    logger.info(f"Baseline Data Health Score: {raw_profile['health_score']}%")

    # Layer 1: Deterministic Cleaning (Pandas & Regex)
    logger.info("[2/4] Running Layer 1 Deterministic Cleaning (Pandas/Regex)...")
    df_det, det_stats = run_deterministic_cleaning(df_raw)

    # Layer 2: Semantic Enrichment (Gemini 3 Flash) & SQLite Load
    logger.info("[3/4] Running Layer 2 Semantic Enrichment (Gemini Agent) & Database Load...")
    agent = DataStewardAgent()
    ai_outputs = agent.enrich_records(df_det)
    df_clean, df_audit = merge_and_load_pipeline(df_det, ai_outputs)
    clean_profile = profile_clean_dataset(df_clean)

    # Executive Analytics & Data Quality Report
    logger.info("[4/4] Computing Governance KPIs and Executive Data Quality Report...")
    kpis = calculate_pipeline_kpis(raw_profile, clean_profile, det_stats, df_clean)
    generate_data_quality_report(kpis, df_audit)

    logger.info(
        f"=== Pipeline Complete! Health Score: {kpis['raw_health_score']}% -> {kpis['clean_health_score']}% "
        f"(+{kpis['health_score_delta']}%) | Auto-Healed: {kpis['auto_healed_rate']}% ==="
    )


if __name__ == "__main__":
    main()