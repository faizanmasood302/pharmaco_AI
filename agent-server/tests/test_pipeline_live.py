import asyncio

from dotenv import load_dotenv

from agents.orchestrator import evaluate_prescription as orchestrate

load_dotenv()


def test_pipeline():
    """Minimal pipeline smoke test — must handle async eval."""
    response = asyncio.run(orchestrate("PGX-001", "Codeine"))

    if response.clinical_narrative:
        pass
    else:
        pass

    for _step in response.agent_steps:
        pass


if __name__ == "__main__":
    test_pipeline()
