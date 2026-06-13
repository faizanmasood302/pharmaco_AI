from dotenv import load_dotenv

from agents.orchestrator import orchestrate

load_dotenv()


def test_pipeline():
    patient_id = "PGX-001"  # Maria Chen
    medication = "Codeine"

    try:
        response = orchestrate(patient_id, medication)

        if response.clinical_narrative:
            pass
        else:
            pass

        for _step in response.agent_steps:
            pass

    except Exception:
        pass


if __name__ == "__main__":
    test_pipeline()
