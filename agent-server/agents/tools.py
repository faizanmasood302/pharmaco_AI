from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Guideline loader — loads CPIC/DPWG per-phenotype recommendations from seed JSON
# ---------------------------------------------------------------------------

_GUIDELINE_DIR = Path(__file__).resolve().parent.parent / "pgx" / "seed"

_GUIDELINE_CACHE: dict[str, dict[str, Any]] | None = None


def _load_guidelines() -> dict[str, dict[str, Any]]:
    global _GUIDELINE_CACHE
    if _GUIDELINE_CACHE is not None:
        return _GUIDELINE_CACHE

    path = _GUIDELINE_DIR / "guidelines.json"
    if not path.exists():
        logger.error("Guideline seed file not found: %s", path)
        _GUIDELINE_CACHE = {}
        return _GUIDELINE_CACHE

    from pgx.seed.schema import GuidelineSeedData

    raw = json.loads(path.read_text(encoding="utf-8"))
    validated = GuidelineSeedData(**raw)

    result: dict[str, dict[str, Any]] = {}
    for dk, entry in validated.guidelines.items():
        result[dk] = {pheno: rec.model_dump() for pheno, rec in entry.phenotypes.items()}

    _GUIDELINE_CACHE = result
    logger.info("Loaded guidelines for %d drugs from %s", len(result), path.name)
    return result


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

    results = query_clinical_knowledge(query, top_k=3, min_similarity=0.3)  # noqa: E501 — matches knowledge.py SIMILARITY_THRESHOLD
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


@register(description="Query CPIC/DPWG clinical guideline for a drug-phenotype pair. Returns evidence-based recommendation with source.")
def query_clinical_guideline(drug: str, phenotype: str) -> str:
    from pgx.rules import DRUG_RULES, normalize_medication

    drug_key = normalize_medication(drug)
    if not drug_key:
        return f"Drug '{drug}' not found in guideline database."

    rule = DRUG_RULES.get(drug_key)
    if not rule:
        return f"No guideline data for '{drug_key}'."

    pheno_key = phenotype.lower().strip()

    drug_guidelines = _load_guidelines().get(drug_key)
    if not drug_guidelines:
        return f"No phenotype-specific guideline data for '{rule.name}'. CPIC level: {rule.cpic_level.value}. Note: {rule.cpic_note}"

    # Match phenotype regardless of exact phrasing
    matched_key = None
    for g_key in drug_guidelines:
        if g_key in pheno_key or pheno_key in g_key:
            matched_key = g_key
            break

    if not matched_key:
        return f"Phenotype '{phenotype}' not found for {rule.name}. Available phenotypes: {', '.join(drug_guidelines.keys())}"

    entry = drug_guidelines[matched_key]
    lines = [
        f"Drug: {rule.name}",
        f"Phenotype: {matched_key.title()}",
        f"Enzyme: {rule.enzyme}",
        f"Is prodrug: {rule.is_prodrug}",
        f"Recommendation: {entry['recommendation']}",
        f"Risk Level: {entry['risk_level']}",
        f"Source: {entry['source']}",
        f"Citation: {entry['citation']}",
    ]
    if entry.get("fda_black_box"):
        lines.append(f"FDA Warning: {entry['fda_black_box']}")

    return "\n".join(lines)


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


@register(description="Normalize a drug name using the NIH RxNorm API. Returns canonical name and RxCUI when found, plus whether the drug is covered by our PGx formulary.")
def normalize_drug_name(drug_name: str) -> str:
    """Use RxNorm API to resolve a drug name to its canonical RxNorm name.

    Returns JSON with:
      - recognized: true/false (RxNorm found it)
      - rxcui: the RxNorm concept ID if found
      - canonical_name: the RxNorm canonical name if found
      - in_formulary: whether we have PGx guidance for this drug
    """
    import json

    from pgx.rules import DRUG_RULES, rxnorm_lookup

    canonical = rxnorm_lookup(drug_name)
    if not canonical:
        return json.dumps({
            "recognized": False,
            "rxcui": None,
            "canonical_name": None,
            "in_formulary": False,
            "message": f"'{drug_name}' not recognized by RxNorm.",
        })

    # Check if canonical name or any alias matches our formulary
    in_formulary = False
    for key, rule in DRUG_RULES.items():
        if canonical == key or canonical in rule.aliases:
            in_formulary = True
            break

    return json.dumps({
        "recognized": True,
        "rxcui": None,
        "canonical_name": canonical,
        "in_formulary": in_formulary,
        "message": (
            f"'{drug_name}' normalized to '{canonical}'. "
            f"{'PGx guidance available.' if in_formulary else 'Not yet covered by PGx guidance.'}"
        ),
    })


# --- Agent-specific tool dispatcher ---


def execute_tool(name: str, tool_input: dict[str, Any]) -> str:
    import json

    if name == "query_patient":
        return _tool_query_patient(tool_input.get("patient_id", ""))
    elif name == "query_evidence":
        return _tool_query_evidence(
            tool_input.get("drug", ""), tool_input.get("phenotype", "")
        )
    elif name == "query_alternative_drugs":
        return _tool_query_alternative_drugs(
            tool_input.get("drug", ""), tool_input.get("phenotype", "")
        )

    # Fall back to registry-based tools
    if name not in _registry:
        return json.dumps({"error": f"Tool '{name}' not found"})
    try:
        result = _registry[name].fn(**tool_input)
        return json.dumps({"result": str(result)})
    except Exception as exc:
        logger.warning("Tool '%s' failed: %s", name, exc)
        return json.dumps({"error": f"Error executing '{name}': {exc}"})


def _tool_query_patient(patient_id: str) -> str:
    """Query patient genetic profile and phenotype."""
    import json

    try:
        from db.database import get_patient_by_id

        patient = get_patient_by_id(patient_id)
        if not patient:
            return json.dumps({"error": f"Patient '{patient_id}' not found"})

        return json.dumps(
            {
                "patient_id": patient.get("id"),
                "display_name": patient.get("display_name"),
                "age": patient.get("age"),
                "sex": patient.get("sex"),
                "indication": patient.get("indication"),
                "cyp_profiles": patient.get("cyp_profiles", []),
            }
        )
    except Exception as exc:
        logger.error("query_patient failed: %s", exc)
        return json.dumps({"error": f"Failed to query patient: {exc}"})


def _tool_query_evidence(drug: str, phenotype: str) -> str:
    """Query clinical evidence for drug-phenotype interaction."""
    import json

    try:
        from agents.therapy_rag import retrieve_therapy_evidence

        evidence, _ = retrieve_therapy_evidence(
            drug, {"phenotype": phenotype}
        )
        return json.dumps(evidence)
    except Exception as exc:
        logger.error("query_evidence failed: %s", exc)
        return json.dumps({"error": f"Failed to query evidence: {exc}"})


def _tool_query_alternative_drugs(drug: str, phenotype: str) -> str:
    """Query alternative medications for given drug-phenotype pair."""
    import json

    try:
        from pgx.rules import DRUG_RULES, normalize_medication

        normalized = normalize_medication(drug)
        if not normalized:
            return json.dumps(
                {
                    "alternatives": [],
                    "reason": f"'{drug}' not in demo formulary",
                }
            )

        rule = DRUG_RULES.get(normalized)
        if not rule or not rule.alternatives:
            return json.dumps({"alternatives": [], "reason": "No alternatives found"})

        phenotype_lower = phenotype.lower()
        alternatives = []
        for alt in rule.alternatives:
            alt_rule = DRUG_RULES.get(alt.lower())
            if alt_rule:
                alternatives.append(
                    {
                        "drug": alt,
                        "enzyme": alt_rule.enzyme,
                        "is_prodrug": alt_rule.is_prodrug,
                        "cpic_note": alt_rule.cpic_note,
                    }
                )

        return json.dumps(
            {
                "alternatives": alternatives,
                "reason": f"Evidence-backed alternatives for {drug} in {phenotype}",
            }
        )
    except Exception as exc:
        logger.error("query_alternative_drugs failed: %s", exc)
        return json.dumps({"error": f"Failed to query alternatives: {exc}"})
