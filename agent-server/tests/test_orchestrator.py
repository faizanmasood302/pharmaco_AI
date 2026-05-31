from agents.orchestrator import orchestrate


def test_orchestrator_adds_challenge_controls_for_critical_risk():
    response = orchestrate("PGX-001", "Codeine")

    assert response.flagged is True
    assert response.agent_verdict == "blocked_by_policy"
    assert response.override_requirement.required is True
    assert "risk_benefit_rationale" in response.override_requirement.required_fields

    assert response.audit_trail
    assert any(step.agent == "Challenge" for step in response.agent_steps)
    assert response.next_best_actions


def test_orchestrator_approves_normal_path_with_monitoring():
    response = orchestrate("PGX-003", "Pregabalin")

    assert response.flagged is False
    assert response.agent_verdict == "approved_with_monitoring"
    assert response.override_requirement.required is False
    assert any("monitoring" in action.lower() for action in response.next_best_actions)
