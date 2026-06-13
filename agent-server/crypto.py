import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


def _is_production() -> bool:
    environment_markers = (
        os.environ.get("ENVIRONMENT"),
        os.environ.get("APP_ENV"),
        os.environ.get("PYTHON_ENV"),
        os.environ.get("RAILWAY_ENVIRONMENT"),
        os.environ.get("VERCEL_ENV"),
    )
    return any(value and value.lower() == "production" for value in environment_markers)


_key = os.environ.get("ENCRYPTION_KEY")

if not _key:
    if _is_production():
        raise RuntimeError("ENCRYPTION_KEY must be set in production.")

    logger.warning(
        "No ENCRYPTION_KEY found. Generating an ephemeral key for local demo mode only."
    )
    _key = Fernet.generate_key().decode()
    os.environ["ENCRYPTION_KEY"] = _key

_cipher_suite = Fernet(_key.encode())


def encrypt_pii(plaintext: str) -> str:
    """Encrypts a string using Fernet symmetric encryption."""
    if not plaintext:
        return ""
    try:
        return _cipher_suite.encrypt(plaintext.encode()).decode()
    except Exception as exc:
        logger.error(f"Encryption failed: {exc}")
        raise ValueError("Failed to encrypt sensitive data") from exc


def decrypt_pii(ciphertext: str) -> str:
    """Decrypts a Fernet encrypted string."""
    if not ciphertext:
        return ""
    try:
        return _cipher_suite.decrypt(ciphertext.encode()).decode()
    except Exception as exc:
        logger.warning(
            "Decryption failed. Falling back to plaintext for seed data: %s",
            exc,
        )
        return ciphertext
