"""Golden-path tests for deterministic PGx rules."""

from pgx.rules import RiskLevel, assess_prescription


def test_ultra_rapid_codeine_critical():
    r = assess_prescription("PGX-001", "Codeine")
    assert r.flagged is True
    assert r.risk_level == RiskLevel.CRITICAL
    assert r.recommended_alternative == "Duloxetine"
    assert r.cpic_level == "strong"


def test_poor_metabolizer_codeine_high():
    r = assess_prescription("PGX-002", "Codeine")
    assert r.flagged is True
    assert r.risk_level == RiskLevel.HIGH


def test_normal_metabolizer_codeine_low():
    r = assess_prescription("PGX-003", "Codeine")
    assert r.flagged is False
    assert r.risk_level == RiskLevel.NONE


def test_pregabalin_no_block():
    r = assess_prescription("PGX-001", "Pregabalin")
    assert r.flagged is False
