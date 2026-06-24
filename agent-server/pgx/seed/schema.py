"""Pydantic models for drug knowledge seed data — validated at load time, fails closed on mismatch."""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class DrugRuleEntry(BaseModel):
    name: str
    aliases: list[str]
    pathway: str
    enzyme: str
    is_prodrug: bool
    alternatives: list[str]
    cpic_level: str
    cpic_note: str
    um_consider_alternative: bool = False
    rule_version: str = "1.0.0"
    cpic_guideline: str = ""
    source_citation: str = ""
    last_reviewed_date: str = ""

    @field_validator("cpic_level")
    @classmethod
    def validate_cpic_level(cls, v: str) -> str:
        allowed = {"strong", "moderate", "optional", "informative"}
        if v.lower() not in allowed:
            raise ValueError(f"cpic_level must be one of {allowed}, got '{v}'")
        return v.lower()


class GuidelineRecommendation(BaseModel):
    recommendation: str
    risk_level: str
    source: str
    citation: str
    fda_black_box: str | None = None

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        allowed = {"low", "moderate", "high"}
        if v.lower() not in allowed:
            raise ValueError(f"risk_level must be one of {allowed}, got '{v}'")
        return v.lower()


class GuidelineEntry(BaseModel):
    phenotypes: dict[str, GuidelineRecommendation]


class DrugSeedData(BaseModel):
    rules: dict[str, DrugRuleEntry]


class GuidelineSeedData(BaseModel):
    guidelines: dict[str, GuidelineEntry]
