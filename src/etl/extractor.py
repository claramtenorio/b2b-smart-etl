import logging
from pathlib import Path
import kagglehub
import pandas as pd
from src.config import RAW_PARTNERS_PATH

logger = logging.getLogger(__name__)


def extract_kaggle_marketplace_data(
    output_path: Path = RAW_PARTNERS_PATH,
    sample_size: int = 12,
    force_download: bool = False,
) -> pd.DataFrame:
    """Downloads marketplace data from Kaggle via kagglehub and prepares a raw B2B onboarding batch"""
    if output_path.exists() and not force_download:
        logger.info(f"Raw dataset already exists at {output_path}. Loading cached raw file.")
        return pd.read_csv(output_path, dtype=str)

    logger.info("Downloading real Brazilian E-Commerce dataset from Kaggle via kagglehub...")
    kaggle_path = Path(kagglehub.dataset_download("olistbr/brazilian-ecommerce"))

    sellers_df = pd.read_csv(kaggle_path / "olist_sellers_dataset.csv")
    items_df = pd.read_csv(kaggle_path / "olist_order_items_dataset.csv")
    products_df = pd.read_csv(kaggle_path / "olist_products_dataset.csv")

    # Join real sellers with their top product categories and total sales volume
    merged = (
        items_df.merge(products_df[["product_id", "product_category_name"]], on="product_id", how="left")
        .groupby("seller_id", as_index=False)
        .agg(
            total_sales=("price", "sum"),
            raw_category=("product_category_name", "first"),
        )
        .merge(sellers_df, on="seller_id", how="inner")
    )

    sample = merged.dropna(subset=["raw_category"]).head(sample_size).copy().reset_index(drop=True)

    # Messy templates simulating unvalidated partner onboarding forms
    messy_cnpjs = [
        "12.345.678/0001-95", "98765432000110", "11.222.333/0001-44", "12345",
        "44.555.666/0001-77", "55666777000188", None, "77.888.999/0001-22",
        "33.444.555/0001-66", "66.777.888/0001-33", "22.333.444/0001-55", "88999000000111"
    ]
    messy_dates = [
        "2026-01-15", "18/02/2026", "2026/03/01", "10-03-2026",
        "2026-03-22", "05/04/2026", "invalid-date", "2026-04-12",
        "19/04/2026", "2026-04-25", "01/05/2026", "2026-05-10"
    ]

    records = []
    for idx, row in sample.iterrows():
        short_id = f"B2B-{1001 + idx}"
        raw_cat = str(row["raw_category"]).replace("_", " ")
        city = str(row["seller_city"]).strip()
        state = str(row["seller_state"]).strip()
        base_val = round(float(row["total_sales"]) * 10, 2)

        # Realistic ingestion formatting noise across rows
        if idx % 4 == 0:
            comp_name = f"  ### {city.upper()} {raw_cat.upper()} COMERCIO E SERVICOS LTDA ###  "
            val_str = f"R$ {base_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            loc_str = f"{city.title()} - {state.upper()}"
            email_str = f"contato@{city.lower().replace(' ', '')}b2b.com.br"
        elif idx % 4 == 1:
            comp_name = f"Expresso {city.title()} Partner ({raw_cat})"
            val_str = f"{round(base_val / 1000, 1)} mil reais"
            loc_str = f"{city.title()} ({state.upper()}) - CEP {row['seller_zip_code_prefix']}"
            email_str = f"FINANCEIRO_{idx}@PARCEIROB2B.COM"
        elif idx % 4 == 2:
            comp_name = f"Grupo {raw_cat.title()} Brasil S/A"
            val_str = f"-{base_val}" if idx == 2 else f"R$ {base_val:.2f}"
            loc_str = f"{city.title()} / {state.upper()}"
            email_str = f"comercial_{idx}_at_b2bpartner.com.br"
        else:
            comp_name = f"Solucoes B2B {city.title()} Ltda"
            val_str = "0" if idx == 7 else f"{base_val:.2f}"
            loc_str = f"Regiao de {city.title()}, Estado: {state.upper()}"
            email_str = f"suporte{idx}@empresa.com.br"

        records.append({
            "partner_id": short_id,
            "company_name": comp_name,
            "tax_id_cnpj": messy_cnpjs[idx % len(messy_cnpjs)],
            "service_description": None if idx == 6 else f"fornecimento corporativo b2b de {raw_cat} (seller kaggle id: {row['seller_id'][:8]})",
            "contract_value": val_str,
            "raw_location": loc_str,
            "onboarding_date": messy_dates[idx % len(messy_dates)],
            "contact_email": email_str,
        })

    # Duplicate row to test deduplication
    records.insert(1, records[0].copy())

    df_raw = pd.DataFrame(records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_raw.to_csv(output_path, index=False)
    logger.info(f"Extracted and saved {len(df_raw)} raw Kaggle marketplace records to {output_path}")
    return df_raw