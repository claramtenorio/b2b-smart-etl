import json
import logging
from typing import List, Dict
import pandas as pd
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY, GEMINI_MODEL, AI_CACHE_PATH
from src.etl.schemas import AIEnrichmentOutput
from src.agents.prompts import build_data_steward_system_prompt

logger = logging.getLogger(__name__)


class BatchAIEnrichmentOutput(BaseModel):
    """Wrapper schema to process multiple partner records in a single LLM API call"""
    results: List[AIEnrichmentOutput]


class DataStewardAgent:
    """Gemini-powered agent for semantic data cleaning, taxonomy mapping, and entity resolution"""

    def __init__(self) -> None:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "your_api_key_here":
            raise ValueError("Missing valid GEMINI_API_KEY in .env file.")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL

    def _load_cache(self) -> Dict[str, AIEnrichmentOutput]:
        if not AI_CACHE_PATH.exists():
            return {}
        try:
            df_cache = pd.read_csv(AI_CACHE_PATH)
            cache: Dict[str, AIEnrichmentOutput] = {}
            for _, row in df_cache.iterrows():
                item = AIEnrichmentOutput(
                    partner_id=str(row["partner_id"]),
                    clean_company_name=str(row["clean_company_name"]),
                    standardized_category=str(row["standardized_category"]),
                    inferred_city=str(row["inferred_city"]),
                    inferred_state=str(row["inferred_state"]),
                    executive_service_summary=str(row["executive_service_summary"]),
                    has_semantic_anomaly=bool(row["has_semantic_anomaly"]),
                    anomaly_notes=str(row["anomaly_notes"]),
                )
                cache[item.partner_id] = item
            return cache
        except Exception as exc:
            logger.warning(f"Could not load AI cache: {exc}. Rebuilding cache.")
            return {}

    def _save_cache(self, cache: Dict[str, AIEnrichmentOutput]) -> None:
        rows = [item.model_dump() for item in cache.values()]
        pd.DataFrame(rows).to_csv(AI_CACHE_PATH, index=False)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=10))
    def _call_gemini_batch(self, payload: List[ dict ]) -> List[AIEnrichmentOutput]:
        prompt = (
            "Sanitize and enrich the following B2B partner records according to the governance rules:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=build_data_steward_system_prompt(),
                response_mime_type="application/json",
                response_schema=BatchAIEnrichmentOutput,
                temperature=0.1,
            ),
        )
        parsed: BatchAIEnrichmentOutput = response.parsed
        return parsed.results

    def enrich_records(self, df_det: pd.DataFrame, force_refresh: bool = False) -> Dict[str, AIEnrichmentOutput]:
        """Enriches deterministic records via Gemini, utilizing local idempotent cache"""
        cache = {} if force_refresh else self._load_cache()
        pending_payload = []

        for _, row in df_det.iterrows():
            pid = str(row["partner_id"])
            if pid not in cache:
                pending_payload.append({
                    "partner_id": pid,
                    "raw_company_name": row["raw_company_name"],
                    "raw_service_description": row["raw_service_description"] or "MISSING_DESCRIPTION",
                    "raw_location": row["raw_location"],
                })

        if not pending_payload:
            logger.info(f"All {len(df_det)} records found in AI cache. Zero API tokens spent!")
            return cache

        logger.info(f"Calling Gemini ({self.model}) in a single batch for {len(pending_payload)} records...")
        batch_outputs = self._call_gemini_batch(pending_payload)

        for item in batch_outputs:
            cache[item.partner_id] = item

        self._save_cache(cache)
        logger.info(f"Successfully enriched and cached {len(batch_outputs)} records via Gemini.")
        return cache