from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., Any]


_registry: dict[str, Tool] = {}


def register(name: str | None = None, description: str | None = None):
    """Decorator that registers a function as a callable tool."""
    def decorator(fn: Callable) -> Callable:
        sig = inspect.signature(fn)
        properties: dict[str, dict[str, str]] = {}
        required: list[str] = []
        for param_name, param in sig.parameters.items():
            properties[param_name] = {"type": "string", "description": f"Parameter: {param_name}"}
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        t = Tool(
            name=name or fn.__name__,
            description=description or fn.__doc__ or "",
            parameters={
                "type": "object",
                "properties": properties,
                "required": required,
            },
            fn=fn,
        )
        _registry[t.name] = t
        return fn

    return decorator


def get_tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in _registry.values()
    ]


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    if name not in _registry:
        return f"Error: tool '{name}' not found"
    try:
        result = _registry[name].fn(**arguments)
        return str(result)
    except Exception as exc:
        logger.warning("Tool '%s' failed: %s", name, exc)
        return f"Error executing '{name}': {exc}"


def list_tools() -> list[str]:
    return sorted(_registry.keys())


# --- Built-in tools ---

@register(description="Look up drug pharmacology and PGx information from the drug database.")
def query_drug_db(medication: str) -> str:
    from pgx.rules import DRUG_RULES, normalize_medication

    normalized = normalize_medication(medication)
    if not normalized:
        return f"Drug '{medication}' not found in the demo formulary."

    rule = DRUG_RULES.get(normalized)
    if not rule:
        return f"No PGx rule found for '{normalized}'."

    return (
        f"Drug: {rule.name}\n"
        f"Enzyme: {rule.enzyme}\n"
        f"Pathway: {rule.pathway}\n"
        f"Is prodrug: {rule.is_prodrug}\n"
        f"Alternatives: {', '.join(rule.alternatives) if rule.alternatives else 'None'}\n"
        f"CPIC level: {rule.cpic_level.value}\n"
        f"CPIC note: {rule.cpic_note}"
    )


@register(description="Retrieve a patient's past evaluation history and prescribing trends.")
def lookup_patient_history(patient_id: str) -> str:
    from db.database import list_evaluations

    evals = list_evaluations(patient_id.upper())
    if not evals:
        return f"No evaluation history found for patient '{patient_id}'."

    lines = [f"Patient: {patient_id}", f"Total evaluations: {len(evals)}", ""]
    for e in evals[-5:]:
        lines.append(f"- {e.get('medication', '?')}: {e.get('risk_level', '?')} (flagged={e.get('flagged', '?')})")
    return "\n".join(lines)


@register(description="Search the clinical knowledge base for pharmacogenomic evidence using semantic search.")
def search_knowledge(query: str) -> str:
    from db.vector_store import query_clinical_knowledge

    results = query_clinical_knowledge(query, top_k=3, min_similarity=0.3)
    if not results:
        return "No relevant knowledge found."

    lines = [f"Found {len(results)} relevant results:", ""]
    for r in results:
        lines.append(f"[{r['source']}] (confidence: {r['similarity']:.2f})")
        lines.append(f"  {r['text'][:200]}")
        lines.append("")
    return "\n".join(lines)


@register(description="Get information about a specific CYP phenotype and its clinical implications.")
def get_phenotype_info(phenotype: str) -> str:
    info = {
        "ultra-rapid metabolizer": "Increased enzyme activity. Risk of toxicity with prodrugs due to excessive active metabolite formation.",
        "poor metabolizer": "Reduced or absent enzyme activity. Risk of treatment failure with prodrugs; increased side effect risk with some drugs.",
        "intermediate metabolizer": "Reduced enzyme activity. May require dose adjustment for some medications.",
        "normal metabolizer": "Normal enzyme activity. Standard dosing applies.",
    }
    key = phenotype.lower().strip()
    for pattern, desc in info.items():
        if pattern in key:
            return f"{phenotype}: {desc}"
    return f"Phenotype '{phenotype}' not found in reference database."


@register(description="Calculate estimated renal function (eGFR) using the Cockcroft-Gault formula.")
def calculate_egfr(age: str, sex: str, creatinine: str, weight_kg: str = "70") -> str:
    try:
        age_val = float(age)
        creat_val = float(creatinine)
        weight_val = float(weight_kg)
    except ValueError:
        return "Error: age, creatinine, and weight_kg must be numeric."

    if creat_val <= 0:
        return "Error: creatinine must be positive."

    crcl = ((140 - age_val) * weight_val) / (72 * creat_val)
    if sex.lower().startswith("f"):
        crcl *= 0.85

    return f"Estimated CrCl: {crcl:.1f} mL/min (Cockcroft-Gault)"
