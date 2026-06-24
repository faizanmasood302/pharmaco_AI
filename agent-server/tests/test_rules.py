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


# --- extract_phenotype contract tests ---
# Guarantees lowercase output so all 4 consumer agents can rely on it

from pgx.patients import extract_phenotype


def test_extract_phenotype_lowercase_ultra_rapid():
    result = extract_phenotype("CYP2D6 Ultra-Rapid Metabolizer")
    assert result == "ultra-rapid metabolizer"


def test_extract_phenotype_lowercase_poor():
    result = extract_phenotype("CYP2D6 Poor Metabolizer")
    assert result == "poor metabolizer"


def test_extract_phenotype_lowercase_normal():
    result = extract_phenotype("CYP2D6 Normal Metabolizer")
    assert result == "normal metabolizer"


def test_extract_phenotype_lowercase_intermediate():
    result = extract_phenotype("CYP2D6 Intermediate Metabolizer")
    assert result == "intermediate metabolizer"


def test_extract_phenotype_default():
    result = extract_phenotype("no phenotype data available")
    assert result == "normal metabolizer"


def test_extract_phenotype_all_lowercase_invariant():
    result = extract_phenotype("cyp2d6 ultra-rapid metabolizer (activity score 2.25)")
    assert result == "ultra-rapid metabolizer"


def test_extract_phenotype_mixed_case():
    result = extract_phenotype("CYP2D6 *1/*1xN Ultra-Rapid Metabolizer")
    assert result == "ultra-rapid metabolizer"


def test_extract_phenotype_embedded():
    result = extract_phenotype("DIAGNOSIS: chronic pain. PHENOTYPE: NORMAL METABOLIZER. PLAN: continue.")
    assert result == "normal metabolizer"
