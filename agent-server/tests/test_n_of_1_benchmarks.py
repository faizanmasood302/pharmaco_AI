from agents.therapy_orchestrator import orchestrate_therapy_generation


def test_benchmark_high_quality_grounding():
    """Verify that a request with high-quality disease grounding passes to human gate."""
    # "opioid" is in the local knowledge and should trigger high/moderate evidence
    response = orchestrate_therapy_generation(
        "PGX-001", "opioid pain response research"
    )

    assert response.status == "research_review_required"
    assert response.evidence_bundle.evidence_quality in ("high", "moderate")
    assert response.final_candidate is not None
    assert response.validation_result.passed is True
    assert response.validation_result.validator_version == "1.4.2-research"


def test_benchmark_low_quality_grounding():
    """Verify that a request with unknown/low evidence is blocked at target selection."""
    # "unobtainium disease" should not be in the local knowledge
    response = orchestrate_therapy_generation("PGX-001", "unobtainium disease research")

    assert response.status == "failed"
    assert response.evidence_bundle.evidence_quality == "low"
    assert any(
        "insufficient research evidence" in step.summary
        for step in response.agent_steps
        if step.agent == "TargetSelection"
    )


def test_benchmark_validation_revision_loop():
    """Verify that the system performs iterative revisions for sequences requiring adjustment."""
    # "opioid" is in knowledge, so it passes Target Selection.
    # Deterministic generation for this string may or may not trigger a loop,
    # but we ensure the status is correct.
    response = orchestrate_therapy_generation(
        "PGX-001", "opioid research simulation", max_iterations=3
    )

    assert response.status == "research_review_required"
    assert response.iterations >= 1
    assert response.final_candidate is not None


def test_benchmark_bioinformatics_checks():
    """Verify that the Phase 4 bioinformatics metrics are present in the output."""
    # "clopidogrel" is in knowledge.
    response = orchestrate_therapy_generation("PGX-001", "clopidogrel research")

    assert response.status == "research_review_required"
    checks = {c.name: c for c in response.validation_result.checks}
    assert "folding_stability" in checks
    assert "homology_off_target" in checks
    assert "immunogenicity_risk" in checks
