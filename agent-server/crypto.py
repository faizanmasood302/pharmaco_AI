import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# In a true production environment, this key would be fetched via AWS KMS or HashiCorp Vault.
# For this MVP, we pull from the environment or generate an ephemeral dev key.
_key = os.environ.get("ENCRYPTION_KEY")

if not _key:
    logger.warning("No ENCRYPTION_KEY found in environment. Generating ephemeral key for local development.")
    _key = Fernet.generate_key().decode()
    os.environ["ENCRYPTION_KEY"] = _key

_cipher_suite = Fernet(_key.encode())

def encrypt_pii(plaintext: str) -> str:
    """Encrypts a string using Fernet symmetric encryption."""
    if not plaintext:
        return ""
    try:
        return _cipher_suite.encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise ValueError("Failed to encrypt sensitive data")

def decrypt_pii(ciphertext: str) -> str:
    """Decrypts a Fernet encrypted string."""
    if not ciphertext:
        return ""
    try:
        return _cipher_suite.decrypt(ciphertext.encode()).decode()
    except Exception as e:
        logger.warning(f"Decryption failed. Falling back to plaintext (for seed data). {e}")
        return ciphertext
