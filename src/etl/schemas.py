from typing import Optional
from pydantic import BaseModel, Field, field_validator
from src.config import OFFICIAL_B2B_CATEGORIES, VALID_BR_STATES


class RawPartnerRecord(BaseModel):
    """Schema representing an incoming dirty B2B partner record extracted from Kaggle"""
    partner_id: str
    company_name: Optional[str] = None
    tax_id_cnpj: Optional[str] = None
    service_description: Optional[str] = None
    contract_value: Optional[str] = None
    raw_location: Optional[str] = None
    onboarding_date: Optional[str] = None
    contact_email: Optional[str] = None


class AIEnrichmentOutput(BaseModel):
    """Structured output contract returned by the Gemini Data Manager Agent"""
    partner_id: str = Field(description="Unique identifier of the partner record")
    clean_company_name: str = Field(description="Standardized name in Title Case without noise")
    standardized_category: str = Field(description="Mapped category from the official B2B taxonomy")
    inferred_city: str = Field(description="Extracted city name in standard Title Case, or 'Unknown'")
    inferred_state: str = Field(description="2-letter Brazilian state abbreviation (UF), or 'NA'")
    executive_service_summary: str = Field(description="Clean, professional 1-sentence summary of the B2B service")
    has_semantic_anomaly: bool = Field(description="True if pricing, description, or identity looks suspicious")
    anomaly_notes: str = Field(description="Short diagnostic note explaining the fix or semantic anomaly")

    @field_validator("standardized_category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in OFFICIAL_B2B_CATEGORIES:
            return "Unclassified"
        return v

    @field_validator("inferred_state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        v_upper = v.strip().upper()
        if v_upper not in VALID_BR_STATES:
            return "NA"
        return v_upper


class CleanPartnerRecord(BaseModel):
    """Final production-ready contract validated before database loading."""
    partner_id: str
    clean_company_name: str
    clean_cnpj: str
    is_cnpj_valid: bool
    standardized_category: str
    executive_service_summary: str
    contract_value_brl: float
    is_value_anomalous: bool
    city: str
    state: str
    onboarding_date_iso: str
    contact_email: str
    needs_manual_review: bool
    resolution_method: str
    audit_notes: str