from pgx.rules import RiskLevel, assess_prescription


def test_risk_matrix_ultra_rapid_codeine(mock_ultra_rapid_patient):
    """CRITICAL: UM + Codeine must be flagged CRITICAL."""
    res = assess_prescription("TEST-UR", "Codeine", patient=mock_ultra_rapid_patient)
    assert res.risk_level == RiskLevel.CRITICAL
    assert res.flagged is True
    assert "toxic metabolite spikes" in res.risk_summary


def test_risk_matrix_poor_metabolizer_codeine(mock_poor_metabolizer_patient):
    """HIGH: PM + Codeine must be flagged HIGH (therapeutic failure)."""
    res = assess_prescription(
        "TEST-PM", "Codeine", patient=mock_poor_metabolizer_patient
    )
    assert res.risk_level == RiskLevel.HIGH
    assert res.flagged is True
    assert "therapeutic failure" in res.risk_summary


def test_risk_matrix_multi_enzyme_hydrocodone(mock_poor_metabolizer_patient):
    """Verify that hydrocodone (CYP2D6 + CYP3A4) handles PM status correctly."""
    # Add a poor CYP3A4 profile to simulate multi-enzyme failure
    mock_poor_metabolizer_patient["cyp_profiles"].append(
        {
            "gene": "CYP3A4",
            "diplotype": "*22/*22",
            "phenotype": "Poor Metabolizer",
            "activity_score": "0.0",
        }
    )
    res = assess_prescription(
        "TEST-PM", "Hydrocodone", patient=mock_poor_metabolizer_patient
    )
    assert res.risk_level == RiskLevel.MODERATE
    assert "CYP3A4 pathway is impaired" in res.risk_summary


def test_risk_matrix_clopidogrel_critical(mock_poor_metabolizer_patient):
    """CRITICAL: PM + Clopidogrel must be flagged CRITICAL."""
    # Update mock to be a CYP2C19 Poor Metabolizer
    mock_poor_metabolizer_patient["cyp_profiles"] = [
        {
            "gene": "CYP2C19",
            "diplotype": "*2/*2",
            "phenotype": "Poor Metabolizer",
            "activity_score": "0.0",
        }
    ]
    res = assess_prescription(
        "TEST-PM", "Clopidogrel", patient=mock_poor_metabolizer_patient
    )
    assert res.risk_level == RiskLevel.CRITICAL
    assert res.flagged is True
