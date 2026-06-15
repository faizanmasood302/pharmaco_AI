from __future__ import annotations

from agents.tracing import (
    DriftMonitor,
    DriftRecord,
    get_drift_monitor,
    traceable,
)


class TestTraceable:
    def test_noop_when_tracing_disabled(self):
        @traceable(name="test_fn")
        def my_fn(x: int) -> int:
            return x * 2

        assert my_fn(5) == 10

    def test_preserves_function(self):
        @traceable()
        def add(a: int, b: int) -> int:
            return a + b

        assert add(3, 4) == 7


class TestDriftRecord:
    def test_no_drift_when_fields_match(self):
        record = DriftRecord(
            agent_name="Test",
            llm_output={"risk_level": "high", "flagged": True},
            fallback_output={"risk_level": "high", "flagged": True},
            field_deltas={},
        )
        assert record.has_drift is False
        assert record.severity == "none"

    def test_drift_detected(self):
        record = DriftRecord(
            agent_name="Test",
            llm_output={"risk_level": "low", "flagged": False},
            fallback_output={"risk_level": "high", "flagged": True},
            field_deltas={"risk_level": ("low", "high"), "flagged": (False, True)},
        )
        assert record.has_drift is True
        assert record.severity == "high"

    def test_low_severity_for_non_critical_fields(self):
        record = DriftRecord(
            agent_name="Test",
            llm_output={"confidence": 0.9},
            fallback_output={"confidence": 0.7},
            field_deltas={"confidence": (0.9, 0.7)},
        )
        assert record.has_drift is True
        assert record.severity == "low"

    def test_to_dict(self):
        record = DriftRecord(
            agent_name="TestAgent",
            llm_output={"risk_level": "low"},
            fallback_output={"risk_level": "high"},
            field_deltas={"risk_level": ("low", "high")},
            context="test case",
        )
        d = record.to_dict()
        assert d["agent"] == "TestAgent"
        assert d["field_deltas"]["risk_level"]["llm"] == "low"
        assert d["field_deltas"]["risk_level"]["fallback"] == "high"
        assert d["context"] == "test case"


class TestDriftMonitor:
    def test_no_drift_initially(self):
        monitor = DriftMonitor()
        summary = monitor.summary()
        assert summary["drift_detected"] is False
        assert summary["record_count"] == 0

    def test_detect_drift_on_mismatch(self):
        monitor = DriftMonitor()
        record = monitor.compare(
            "TestAgent",
            {"risk_level": "low", "flagged": False},
            {"risk_level": "high", "flagged": True},
        )
        assert record.has_drift is True
        assert len(monitor.records) == 1

    def test_no_drift_on_match(self):
        monitor = DriftMonitor()
        record = monitor.compare(
            "TestAgent",
            {"risk_level": "high", "flagged": True},
            {"risk_level": "high", "flagged": True},
        )
        assert record.has_drift is False
        assert len(monitor.records) == 0

    def test_tracks_multiple_records(self):
        monitor = DriftMonitor()
        monitor.compare(
            "A", {"risk_level": "low"}, {"risk_level": "high"},
        )
        monitor.compare(
            "B", {"risk_level": "low"}, {"risk_level": "low"},
        )
        monitor.compare(
            "C", {"flagged": True}, {"flagged": False},
        )
        assert len(monitor.records) == 2

    def test_summary_counts_severity(self):
        monitor = DriftMonitor()
        monitor.compare(
            "A",
            {"risk_level": "low", "flagged": False},
            {"risk_level": "high", "flagged": True},
        )
        monitor.compare(
            "B",
            {"confidence": 0.9},
            {"confidence": 0.7},
            tracked_fields=["confidence"],
        )
        monitor.compare(
            "C",
            {"risk_level": "low"},
            {"risk_level": "high"},
        )
        summary = monitor.summary()
        assert summary["record_count"] == 3
        assert summary["high_severity"] == 2
        assert summary["low_severity"] == 1

    def test_compare_with_none_llm_output(self):
        monitor = DriftMonitor()
        record = monitor.compare(
            "TestAgent",
            None,
            {"risk_level": "high", "flagged": True},
        )
        assert record.has_drift is False

    def test_compare_custom_tracked_fields(self):
        monitor = DriftMonitor()
        record = monitor.compare(
            "TestAgent",
            {"risk_level": "low", "flagged": False, "confidence": 0.9},
            {"risk_level": "low", "flagged": False, "confidence": 0.7},
            tracked_fields=["confidence"],
        )
        assert record.has_drift is True
        assert "confidence" in record.field_deltas

    def test_get_drift_monitor_singleton(self):
        m1 = get_drift_monitor()
        m2 = get_drift_monitor()
        assert m1 is m2

    def test_drift_record_in_summary(self):
        monitor = DriftMonitor()
        monitor.compare(
            "TestAgent",
            {"risk_level": "low"},
            {"risk_level": "critical"},
            context="codeine/UR",
        )
        summary = monitor.summary()
        assert len(summary["records"]) == 1
        assert summary["records"][0]["agent"] == "TestAgent"
        assert summary["records"][0]["context"] == "codeine/UR"
