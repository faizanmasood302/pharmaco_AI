import os

from dotenv import load_dotenv

load_dotenv()

# AI / LLM Configuration
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# Security Configuration
SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = "HS256"

# Database Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

# API Configuration
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

# Demo Credentials (FIX #1.5)
# In production, these would be in a secure database with hashed passwords
import hashlib
def _hash_pass(p): return hashlib.sha256(p.encode()).hexdigest()

DEMO_DOCTORS = {
    "doctor@clinic.com": _hash_pass("testpass"),
    "admin@genomiclens.com": _hash_pass("admin123")
}
