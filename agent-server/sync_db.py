import logging
import os
import sys

# Add agent-server to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.supabase import upsert_patient
from pgx.patients import PATIENTS

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("Syncing local mock patients to Supabase...")
    for pid, patient in PATIENTS.items():
        logger.info("Upserting %s...", pid)
        try:
            upsert_patient(patient)
            logger.info("Successfully upserted %s", pid)
        except Exception:
            logger.exception("Failed to upsert %s", pid)
    logger.info("Sync complete.")


if __name__ == "__main__":
    main()
