from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

KNOWLEDGE_PATCH = "agents.knowledge.query_clinical_knowledge"
THERAPY_PATCH = "agents.therapy_rag.query_clinical_knowledge"


@pytest.fixture(autouse=True)
def no_groq(monkeypatch):
    monkeypatch.setattr("agents.knowledge._groq", None)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)


class TestRetrieveClinicalEvidence:
    def test_semantic_retrieval_returns_hits(self):
        semantic_hits = [
            {
                "source": "cpic_opioid_guidelines.md",
                "chunk_id": "cpic_opioid_guidelines.md:1",
                "text": "Avoid codeine in ultra-rapid metabolizers due to toxicity risk.",
                "similarity": 0.72,
                "distance": 0.28,
            }
        ]
        with patch(KNOWLEDGE_PATCH, return_value=semantic_hits):
            from agents.knowledge import retrieve_clinical_evidence

            result, elapsed, sources = retrieve_clinical_evidence(
                "Codeine", "Ultra-Rapid Metabolizer", "CRITICAL"
            )

        assert result is not None
        assert "cpic_opioid_guidelines.md" in result
        assert sources == ["cpic_opioid_guidelines.md"]
        assert elapsed >= 0

    def test_semantic_retrieval_multiple_sources(self):
        semantic_hits = [
            {
                "source": "cpic_opioid_guidelines.md",
                "chunk_id": "1",
                "text": "Avoid codeine in UMs.",
                "similarity": 0.68,
                "distance": 0.32,
            },
            {
                "source": "pharmgkb_metabolic_summary.md",
                "chunk_id": "2",
                "text": "CYP2D6 UM phenotype leads to increased morphine conversion.",
                "similarity": 0.55,
                "distance": 0.45,
            },
        ]
        with patch(KNOWLEDGE_PATCH, return_value=semantic_hits):
            from agents.knowledge import retrieve_clinical_evidence

            result, elapsed, sources = retrieve_clinical_evidence(
                "Codeine", "Ultra-Rapid Metabolizer", "CRITICAL"
            )

        assert sources == [
            "cpic_opioid_guidelines.md",
            "pharmgkb_metabolic_summary.md",
        ]

    def test_keyword_fallback_when_semantic_empty(self):
        with patch(KNOWLEDGE_PATCH, return_value=[]):
            from agents.knowledge import retrieve_clinical_evidence

            result, elapsed, sources = retrieve_clinical_evidence(
                "Codeine", "Ultra-Rapid Metabolizer", "CRITICAL"
            )

        assert result is not None
        assert "codeine" in result.lower()

    def test_external_db_fallback_when_no_local_match(self):
        with patch(KNOWLEDGE_PATCH, return_value=[]):
            from agents.knowledge import retrieve_clinical_evidence

            result, elapsed, sources = retrieve_clinical_evidence(
                "MadeUpDrug", "Unknown Phenotype", "LOW"
            )

        assert result is not None
        assert elapsed >= 0
        assert isinstance(sources, list)

    def test_uses_groq_when_available(self):
        mock_groq = MagicMock()
        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Source: cpic_opioid_guidelines.md\nAvoid codeine in UMs."
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]

        semantic_hits = [
            {
                "source": "cpic_opioid_guidelines.md",
                "chunk_id": "1",
                "text": "Avoid codeine in UMs.",
                "similarity": 0.72,
                "distance": 0.28,
            }
        ]

        mock_groq.chat.completions.create.return_value = mock_completion

        with (
            patch(KNOWLEDGE_PATCH, return_value=semantic_hits),
            patch("agents.knowledge._groq", mock_groq),
            patch.dict(os.environ, {"GROQ_API_KEY": "mock-key"}, clear=False),
        ):
            from agents.knowledge import retrieve_clinical_evidence

            result, elapsed, sources = retrieve_clinical_evidence(
                "Codeine", "Ultra-Rapid Metabolizer", "CRITICAL"
            )

        assert result is not None
        assert "Source:" in str(result)


class TestRetrieveTherapyEvidence:
    def test_semantic_retrieval_returns_high_quality(self):
        semantic_hits = [
            {
                "source": "n_of_1_research_simulation_policy.md",
                "chunk_id": "1",
                "text": "mRNA therapy candidate validation protocol for n-of-1 research.",
                "similarity": 0.65,
                "distance": 0.35,
            },
            {
                "source": "cpic_opioid_guidelines.md",
                "chunk_id": "2",
                "text": "Opioid pain response research target for mRNA therapy.",
                "similarity": 0.55,
                "distance": 0.45,
            },
        ]
        with patch(THERAPY_PATCH, return_value=semantic_hits):
            from agents.therapy_rag import retrieve_therapy_evidence

            result, elapsed = retrieve_therapy_evidence(
                "opioid pain response research",
                {"indication": "Pain", "cyp_profiles": []},
            )

        assert result["sources"] == [
            "cpic_opioid_guidelines.md",
            "n_of_1_research_simulation_policy.md",
        ]
        assert result["evidence_quality"] == "high"
        assert len(result["source_snippets"]) == 2
        assert elapsed >= 0

    def test_semantic_retrieval_returns_moderate_quality(self):
        semantic_hits = [
            {
                "source": "cpic_opioid_guidelines.md",
                "chunk_id": "1",
                "text": "Opioid pain response research target for mRNA therapy.",
                "similarity": 0.42,
                "distance": 0.58,
            }
        ]
        with patch(THERAPY_PATCH, return_value=semantic_hits):
            from agents.therapy_rag import retrieve_therapy_evidence

            result, elapsed = retrieve_therapy_evidence(
                "opioid pain response research",
                {"indication": "Pain", "cyp_profiles": []},
            )

        assert result["evidence_quality"] == "moderate"

    def test_semantic_retrieval_returns_low_quality(self):
        semantic_hits = [
            {
                "source": "cpic_opioid_guidelines.md",
                "chunk_id": "1",
                "text": "General metabolic information about CYP enzymes.",
                "similarity": 0.27,
                "distance": 0.73,
            }
        ]
        with patch(THERAPY_PATCH, return_value=semantic_hits):
            from agents.therapy_rag import retrieve_therapy_evidence

            result, elapsed = retrieve_therapy_evidence(
                "unrelated disease",
                {"indication": "Unknown", "cyp_profiles": []},
            )

        assert result["evidence_quality"] == "low"

    def test_low_quality_when_no_disease_overlap(self):
        semantic_hits = [
            {
                "source": "fda_safety_labels.md",
                "chunk_id": "1",
                "text": "General safety labeling information.",
                "similarity": 0.45,
                "distance": 0.55,
            }
        ]
        with patch(THERAPY_PATCH, return_value=semantic_hits):
            from agents.therapy_rag import retrieve_therapy_evidence

            result, elapsed = retrieve_therapy_evidence(
                "zebrafish retinal regeneration",
                {"indication": "Vision research", "cyp_profiles": []},
            )

        assert result["sources"] == []
        assert result["evidence_quality"] == "low"
        assert "No disease-specific evidence" in result["target_rationale"]

    def test_keyword_fallback_when_semantic_empty(self):
        with patch(THERAPY_PATCH, return_value=[]):
            from agents.therapy_rag import retrieve_therapy_evidence

            result, elapsed = retrieve_therapy_evidence(
                "opioid pain response research",
                {"indication": "Pain", "cyp_profiles": []},
            )

        assert result["sources"]
        assert result["evidence_quality"] in ("high", "moderate")

    def test_low_quality_fallback_when_no_keyword_match(self):
        with patch(THERAPY_PATCH, return_value=[]):
            from agents.therapy_rag import retrieve_therapy_evidence

            result, elapsed = retrieve_therapy_evidence(
                "xyzwxyz nonexistent zygohistomorphic",
                {"indication": "Rare disease", "cyp_profiles": []},
            )

        assert result["sources"] == []
        assert result["evidence_quality"] == "low"

    def test_semantic_query_includes_phenotype_context(self):
        with patch(THERAPY_PATCH, return_value=[]) as mock_query:
            from agents.therapy_rag import retrieve_therapy_evidence

            retrieve_therapy_evidence(
                "pain research",
                {
                    "indication": "Pain",
                    "cyp_profiles": [
                        {
                            "gene": "CYP2D6",
                            "phenotype": "Poor Metabolizer",
                        }
                    ],
                },
            )

        call_args = mock_query.call_args
        assert call_args is not None
        call_query = call_args[0][0]
        assert "pain research" in call_query
        assert "Poor Metabolizer" in call_query
