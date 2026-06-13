import json
from pathlib import Path

from fhir.parser import parse_fhir_bundle

FIXTURE = (
    Path(__file__).resolve().parent.parent / "fixtures" / "ultra_rapid_patient.json"
)


def test_parse_ultra_rapid_fixture():
    bundle = json.loads(FIXTURE.read_text())
    patient = parse_fhir_bundle(bundle)
    assert patient["display_name"] == "Alex Rivera"
    assert patient["cyp_profiles"][0]["phenotype"] == "Ultra-Rapid Metabolizer"
