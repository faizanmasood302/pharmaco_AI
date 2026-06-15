from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agents.tools import (
    _registry,
    execute_tool,
    get_tool_schemas,
    list_tools,
    register,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Remove custom tools after each test while keeping built-in tools."""
    builtin_names = {
        "query_drug_db",
        "lookup_patient_history",
        "search_knowledge",
        "get_phenotype_info",
        "calculate_egfr",
    }
    yield
    for name in list(_registry):
        if name not in builtin_names:
            del _registry[name]


@pytest.fixture
def empty_registry():
    """Temporarily clear all tools (including built-ins) for framework tests."""
    saved = dict(_registry)
    _registry.clear()
    yield
    _registry.clear()
    _registry.update(saved)


def test_register_decorator_adds_tool(empty_registry):
    @register()
    def my_tool(param1: str) -> str:
        return f"got {param1}"

    assert "my_tool" in _registry
    assert _registry["my_tool"].name == "my_tool"
    assert _registry["my_tool"].fn is my_tool


def test_register_custom_name(empty_registry):
    @register(name="custom_name")
    def some_fn(x: str) -> str:
        return x

    assert "custom_name" in _registry
    assert "some_fn" not in _registry


def test_register_custom_description(empty_registry):
    @register(description="Does something useful")
    def useful_tool(data: str) -> str:
        return data

    assert _registry["useful_tool"].description == "Does something useful"


def test_register_infers_parameters(empty_registry):
    @register()
    def add(a: str, b: str) -> str:
        return str(int(a) + int(b))

    params = _registry["add"].parameters
    assert params["type"] == "object"
    assert "a" in params["properties"]
    assert "b" in params["properties"]
    assert params["required"] == ["a", "b"]


def test_register_optional_parameter(empty_registry):
    @register()
    def greet(name: str, greeting: str = "Hello") -> str:
        return f"{greeting}, {name}!"

    params = _registry["greet"].parameters
    assert params["required"] == ["name"]


def test_execute_tool_success(empty_registry):
    @register()
    def double(x: str) -> str:
        return str(int(x) * 2)

    result = execute_tool("double", {"x": "5"})
    assert result == "10"


def test_execute_tool_not_found(empty_registry):
    result = execute_tool("nonexistent", {})
    assert "not found" in result


def test_execute_tool_error(empty_registry):
    @register()
    def broken(x: str) -> str:
        raise ValueError("something broke")

    result = execute_tool("broken", {"x": "1"})
    assert "Error" in result
    assert "broken" in result


def test_get_tool_schemas_empty(empty_registry):
    assert get_tool_schemas() == []


def test_get_tool_schemas_returns_list(empty_registry):
    @register(name="test_tool", description="A test tool")
    def tool_fn(x: str) -> str:
        return x

    schemas = get_tool_schemas()
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "test_tool"
    assert schemas[0]["function"]["description"] == "A test tool"


def test_list_tools(empty_registry):
    @register(name="alpha")
    def alpha_fn(): ...

    @register(name="beta")
    def beta_fn(): ...

    assert list_tools() == ["alpha", "beta"]


class TestQueryDrugDb:
    def test_finds_known_drug(self):
        result = execute_tool("query_drug_db", {"medication": "codeine"})
        assert "Codeine" in result
        assert "CYP2D6" in result
        assert "prodrug" in result

    def test_finds_known_drug_alias(self):
        result = execute_tool("query_drug_db", {"medication": "tylenol with codeine"})
        assert "Codeine" in result
        assert "CYP2D6" in result

    def test_unknown_drug(self):
        result = execute_tool("query_drug_db", {"medication": "nonexistent"})
        assert "not found" in result


class TestLookupPatientHistory:
    def test_with_history(self):
        mock_evals = [
            {"medication": "Codeine", "risk_level": "critical", "flagged": True},
            {"medication": "Tramadol", "risk_level": "high", "flagged": True},
        ]
        with patch("db.database.list_evaluations", return_value=mock_evals):
            result = execute_tool("lookup_patient_history", {"patient_id": "PGX-001"})
        assert "PGX-001" in result
        assert "Codeine" in result
        assert "Tramadol" in result

    def test_no_history(self):
        with patch("db.database.list_evaluations", return_value=[]):
            result = execute_tool("lookup_patient_history", {"patient_id": "PGX-999"})
        assert "No evaluation history" in result


class TestSearchKnowledge:
    def test_returns_hits(self):
        mock_hits = [
            {
                "source": "cpic_opioid_guidelines.md",
                "chunk_id": "1",
                "text": "Avoid codeine in ultra-rapid metabolizers.",
                "similarity": 0.72,
                "distance": 0.28,
            }
        ]
        with patch("db.vector_store.query_clinical_knowledge", return_value=mock_hits):
            result = execute_tool("search_knowledge", {"query": "codeine"})
        assert "cpic_opioid_guidelines.md" in result
        assert "0.72" in result

    def test_no_hits(self):
        with patch("db.vector_store.query_clinical_knowledge", return_value=[]):
            result = execute_tool("search_knowledge", {"query": "zzzznonexistent"})
        assert "No relevant knowledge" in result


class TestGetPhenotypeInfo:
    def test_known_phenotype(self):
        result = execute_tool(
            "get_phenotype_info", {"phenotype": "Ultra-Rapid Metabolizer"}
        )
        assert "Ultra-Rapid Metabolizer" in result
        assert "toxicity" in result

    def test_unknown_phenotype(self):
        result = execute_tool(
            "get_phenotype_info", {"phenotype": "Mega Metabolizer"}
        )
        assert "not found" in result


class TestCalculateEgfr:
    def test_male_default_weight(self):
        result = execute_tool(
            "calculate_egfr", {"age": "40", "sex": "M", "creatinine": "1.0"}
        )
        assert "CrCl" in result
        assert "mL/min" in result

    def test_female_adjustment(self):
        result_m = execute_tool(
            "calculate_egfr", {"age": "40", "sex": "M", "creatinine": "1.0", "weight_kg": "70"}
        )
        result_f = execute_tool(
            "calculate_egfr", {"age": "40", "sex": "F", "creatinine": "1.0", "weight_kg": "70"}
        )
        m_value = float(result_m.split(":")[1].strip().split()[0])
        f_value = float(result_f.split(":")[1].strip().split()[0])
        assert f_value < m_value

    def test_invalid_input(self):
        result = execute_tool(
            "calculate_egfr", {"age": "forty", "sex": "M", "creatinine": "1.0"}
        )
        assert "Error" in result
