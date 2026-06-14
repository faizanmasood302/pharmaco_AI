import os

from dotenv import load_dotenv

load_dotenv()

# AI / LLM Configuration
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# Security Configuration
SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = "HS256"

# API Configuration
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",")
