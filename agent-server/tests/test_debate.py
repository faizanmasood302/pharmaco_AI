from __future__ import annotations

from unittest.mock import patch

import pytest

from models import AdjudicatorOutput, SpecialistOpinion


@pytest.fixture
def ur_patient():
    return {
        "id": "TEST-UR",
        "display_name": "Test UR",
        "age": 30,
        "sex": "F",
        "indication": "Pain",
        "cyp_profiles": [
            {
                "gene": "CYP2D6",
                "diplotype": "*1/*1xN",
                "phenotype": "Ultra-Rapid Metabolizer",
                "activity_score": "3.0",
            }
        ],
    }


@pytest.fixture
def pm_patient():
    return {
        "id": "TEST-PM",
        "display_name": "Test PM",
        "age": 45,
        "sex": "M",
        "indication": "Pain",
        "cyp_profiles": [
            {
                "gene": "CYP2D6",
                "diplotype": "*4/*4",
                "phenotype": "Poor Metabolizer",
                "activity_score": "0.0",
            }
        ],
    }


@pytest.fixture
def normal_patient():
    return {
        "id": "TEST-NM",
        "display_name": "Test NM",
        "age": 35,
        "sex": "F",
        "indication": "Pain",
        "cyp_profiles": [
            {
                "gene": "CYP2D6",
                "diplotype": "*1/*1",
                "phenotype": "Normal Metabolizer",
                "activity_score": "1.0",
            }
        ],
    }


class TestPharmacologistFallback:
    def test_ur_prodrug_critical(self):
        from agents.debate import _pharmacologist_fallback

        result = _pharmacologist_fallback("Codeine", "Ultra-Rapid Metabolizer", "Avoid codeine.")
        assert result.risk_level == "critical"
        assert result.flagged is True
        assert result.recommendation == "Duloxetine"

    def test_pm_prodrug_high(self):
        from agents.debate import _pharmacologist_fallback

        result = _pharmacologist_fallback("Codeine", "Poor Metabolizer", "Reduced activation.")
        assert result.risk_level == "high"
        assert result.flagged is True
        assert result.recommendation == "Pregabalin"

    def test_unknown_drug_low(self):
        from agents.debate import _pharmacologist_fallback

        result = _pharmacologist_fallback("Windex", "Ultra-Rapid Metabolizer", None)
        assert result.flagged is False
        assert "not in the demo formulary" in result.risk_summary.lower()

    def test_compatible_drug_low(self):
        from agents.debate import _pharmacologist_fallback

        result = _pharmacologist_fallback("Pregabalin", "Normal Metabolizer", None)
        assert result.flagged is False
        assert result.risk_level == "low"

    def test_evidence_with_caution_moderate(self):
        from agents.debate import _pharmacologist_fallback

        result = _pharmacologist_fallback("Hydrocodone", "Poor Metabolizer", "caution advised")
        assert result.flagged is True
        assert result.risk_level == "moderate"


class TestGeneticistFallback:
    def test_ur_with_prodrug_signals_high(self):
        from agents.debate import _geneticist_fallback

        result = _geneticist_fallback("Ultra-Rapid Metabolizer", "Codeine is a prodrug.")
        assert result.flagged is True
        assert result.risk_level == "high"

    def test_ur_without_prodrug_low(self):
        from agents.debate import _geneticist_fallback

        result = _geneticist_fallback("Ultra-Rapid Metabolizer", "General info about metabolism.")
        assert result.flagged is False
        assert result.risk_level == "low"

    def test_pm_with_prodrug_high(self):
        from agents.debate import _geneticist_fallback

        result = _geneticist_fallback("Poor Metabolizer", "Tramadol activation requires CYP2D6.")
        assert result.flagged is True
        assert result.risk_level == "high"

    def test_normal_no_risk(self):
        from agents.debate import _geneticist_fallback

        result = _geneticist_fallback("Normal Metabolizer", None)
        assert result.flagged is False
        assert result.risk_level == "none"

    def test_intermediate_no_caution_low(self):
        from agents.debate import _geneticist_fallback

        result = _geneticist_fallback("Intermediate Metabolizer", "No concerns noted.")
        assert result.flagged is False
        assert result.risk_level == "low"


class TestClinicianFallback:
    def test_medication_specific_concern(self):
        from agents.debate import _clinician_fallback

        result = _clinician_fallback(
            {"indication": "Pain", "age": 30}, "Codeine", "Avoid codeine in UMs."
        )
        assert result.flagged is True
        assert result.risk_level == "moderate"

    def test_general_caution_not_medication_specific(self):
        from agents.debate import _clinician_fallback

        result = _clinician_fallback(
            {"indication": "Pain", "age": 30}, "Pregabalin", "Avoid codeine, critical risk."
        )
        assert result.flagged is False
        assert result.risk_level == "low"

    def test_no_concerns(self):
        from agents.debate import _clinician_fallback

        result = _clinician_fallback(
            {"indication": "Pain", "age": 35}, "Pregabalin", None
        )
        assert result.flagged is False
        assert result.risk_level == "none"

    def test_pediatric_flag(self):
        from agents.debate import _clinician_fallback

        result = _clinician_fallback(
            {"indication": "Pain", "age": 12}, "Codeine", None
        )
        assert result.flagged is False
        assert result.risk_level == "low"


class TestAdjudicatorFallback:
    def test_unanimous_agreement(self):
        from agents.debate import _adjudicator_fallback

        opinions = [
            SpecialistOpinion(agent_name="A", risk_level="critical", flagged=True, risk_summary="x", reasoning="x", confidence=0.9),
            SpecialistOpinion(agent_name="B", risk_level="critical", flagged=True, risk_summary="x", reasoning="x", confidence=0.9),
            SpecialistOpinion(agent_name="C", risk_level="critical", flagged=True, risk_summary="x", reasoning="x", confidence=0.9),
        ]
        result = _adjudicator_fallback(opinions)
        assert result.agreement_level == "unanimous"
        assert result.consensus_risk_level == "critical"
        assert result.consensus_flagged is True

    def test_majority_agreement(self):
        from agents.debate import _adjudicator_fallback

        opinions = [
            SpecialistOpinion(agent_name="A", risk_level="high", flagged=True, risk_summary="x", reasoning="x", confidence=0.9),
            SpecialistOpinion(agent_name="B", risk_level="high", flagged=True, risk_summary="x", reasoning="x", confidence=0.9),
            SpecialistOpinion(agent_name="C", risk_level="low", flagged=False, risk_summary="x", reasoning="x", confidence=0.8),
        ]
        result = _adjudicator_fallback(opinions)
        assert result.agreement_level == "majority"
        assert result.consensus_risk_level == "high"
        assert result.consensus_flagged is True

    def test_takes_highest_risk(self):
        from agents.debate import _adjudicator_fallback

        opinions = [
            SpecialistOpinion(agent_name="A", risk_level="critical", flagged=True, risk_summary="x", reasoning="x", confidence=0.9),
            SpecialistOpinion(agent_name="B", risk_level="moderate", flagged=True, risk_summary="x", reasoning="x", confidence=0.8),
            SpecialistOpinion(agent_name="C", risk_level="low", flagged=False, risk_summary="x", reasoning="x", confidence=0.8),
        ]
        result = _adjudicator_fallback(opinions)
        assert result.consensus_risk_level == "critical"
        assert result.consensus_flagged is True

    def test_no_risk_all_none(self):
        from agents.debate import _adjudicator_fallback

        opinions = [
            SpecialistOpinion(agent_name="A", risk_level="none", flagged=False, risk_summary="x", reasoning="x", confidence=0.9),
            SpecialistOpinion(agent_name="B", risk_level="none", flagged=False, risk_summary="x", reasoning="x", confidence=0.9),
            SpecialistOpinion(agent_name="C", risk_level="low", flagged=False, risk_summary="x", reasoning="x", confidence=0.85),
        ]
        result = _adjudicator_fallback(opinions)
        assert result.consensus_flagged is False


class TestConvenePanel:
    def test_convenes_three_specialists_with_fallbacks(self, ur_patient):
        from agents.debate import convene_panel

        with patch("agents.debate._groq", None):
            opinions, adjudicated, elapsed = convene_panel(
                ur_patient, "Codeine", "Avoid codeine in UMs.", ["cpic_guidelines.md"]
            )

        assert len(opinions) == 3
        agent_names = {o.agent_name for o in opinions}
        assert agent_names == {"Pharmacologist", "Geneticist", "Clinician"}
        assert adjudicated.consensus_risk_level == "critical"
        assert adjudicated.consensus_flagged is True
        assert elapsed >= 0

    def test_panel_safe_case(self, normal_patient):
        from agents.debate import convene_panel

        with patch("agents.debate._groq", None):
            opinions, adjudicated, elapsed = convene_panel(
                normal_patient, "Pregabalin", None, []
            )

        assert len(opinions) == 3
        assert adjudicated.consensus_flagged is False

    def test_panel_pm_case(self, pm_patient):
        from agents.debate import convene_panel

        with patch("agents.debate._groq", None):
            opinions, adjudicated, elapsed = convene_panel(
                pm_patient, "Tramadol", "Tramadol activation requires CYP2D6.", ["cpic_guidelines.md"]
            )

        assert adjudicated.consensus_flagged is True
        assert adjudicated.consensus_risk_level in ("high", "critical")
