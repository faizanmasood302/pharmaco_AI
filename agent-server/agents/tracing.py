from __future__ import annotations

import logging
import os
from typing import Any, Callable

logger = logging.getLogger(__name__)

TRACING_ENABLED = os.environ.get("LANGSMITH_TRACING", "").lower() in (
    "true",
    "1",
    "yes",
)
PROJECT_NAME = os.environ.get("LANGSMITH_PROJECT", "pharmacogenomic-harness")

try:
    from langsmith import traceable as _langsmith_traceable
    from langsmith.run_trees import RunTree

    _langsmith_available = True
except ImportError:
    _langsmith_available = False


def traceable(
    name: str | None = None,
    run_type: str = "chain",
) -> Callable:
    """Decorator that wraps a function with LangSmith tracing when enabled.

    When LANGSMITH_TRACING is not set or langsmith is not installed,
    this acts as a no-op pass-through.
    """
    if TRACING_ENABLED and _langsmith_available:
        return _langsmith_traceable(name=name, run_type=run_type)
    return lambda fn: fn


class DriftRecord:
    """Records a drift detection event when LLM output diverges from deterministic baseline."""

    def __init__(
        self,
        agent_name: str,
        llm_output: dict[str, Any] | None,
        fallback_output: dict[str, Any],
        field_deltas: dict[str, tuple[Any, Any]],
        context: str = "",
    ) -> None:
        self.agent_name = agent_name
        self.llm_output = llm_output
        self.fallback_output = fallback_output
        self.field_deltas = field_deltas
        self.context = context

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent_name,
            "field_deltas": {
                k: {"llm": v[0], "fallback": v[1]} for k, v in self.field_deltas.items()
            },
            "context": self.context,
        }

    @property
    def has_drift(self) -> bool:
        return len(self.field_deltas) > 0

    @property
    def severity(self) -> str:
        risk_fields = {"risk_level", "flagged"}
        critical_deltas = risk_fields & set(self.field_deltas.keys())
        if critical_deltas:
            return "high"
        if self.field_deltas:
            return "low"
        return "none"


class DriftMonitor:
    """Compares LLM agent outputs against deterministic fallback baselines.

    Flags cases where the LLM diverges from the rule-based system on
    key clinical decisions (risk_level, flagged status).
    """

    def __init__(self) -> None:
        self.records: list[DriftRecord] = []

    def compare(
        self,
        agent_name: str,
        llm_output: dict[str, Any] | None,
        fallback_output: dict[str, Any],
        tracked_fields: list[str] | None = None,
        context: str = "",
    ) -> DriftRecord:
        if tracked_fields is None:
            tracked_fields = ["risk_level", "flagged"]

        field_deltas: dict[str, tuple[Any, Any]] = {}

        for field in tracked_fields:
            llm_val = llm_output.get(field) if llm_output else None
            fb_val = fallback_output.get(field)
            if llm_val is not None and str(llm_val) != str(fb_val):
                field_deltas[field] = (llm_val, fb_val)

        record = DriftRecord(
            agent_name=agent_name,
            llm_output=llm_output,
            fallback_output=fallback_output,
            field_deltas=field_deltas,
            context=context,
        )

        if record.has_drift:
            logger.warning(
                "Drift detected in %s — fields: %s (severity=%s)",
                agent_name,
                list(field_deltas.keys()),
                record.severity,
            )
            self.records.append(record)

        return record

    def summary(self) -> dict[str, Any]:
        if not self.records:
            return {"drift_detected": False, "record_count": 0}
        return {
            "drift_detected": True,
            "record_count": len(self.records),
            "high_severity": sum(1 for r in self.records if r.severity == "high"),
            "low_severity": sum(1 for r in self.records if r.severity == "low"),
            "records": [r.to_dict() for r in self.records],
        }


_monitor: DriftMonitor | None = None


def get_drift_monitor() -> DriftMonitor:
    global _monitor
    if _monitor is None:
        _monitor = DriftMonitor()
    return _monitor


def create_trace(
    name: str,
    inputs: dict[str, Any] | None = None,
    run_type: str = "chain",
) -> Any | None:
    """Create a manual LangSmith trace run.

    Returns a RunTree if LangSmith is enabled, None otherwise.
    """
    if not TRACING_ENABLED or not _langsmith_available:
        return None
    try:
        return RunTree(
            name=name,
            run_type=run_type,
            inputs=inputs or {},
        )
    except Exception as exc:
        logger.debug("Failed to create LangSmith trace: %s", exc)
        return None


def end_trace(trace: Any, outputs: dict[str, Any] | None = None) -> None:
    """End a manual LangSmith trace run."""
    if trace is None:
        return
    try:
        if outputs:
            trace.end(outputs=outputs)
        else:
            trace.end()
        trace.post()
    except Exception as exc:
        logger.debug("Failed to end LangSmith trace: %s", exc)
