"""Structured seed data for pharmacogenomic drug rules and guidelines.

All drug knowledge is stored in version-controlled JSON files and validated
against Pydantic schemas at load time. The server fails closed on invalid
seed data — a malformed entry will prevent startup.

Use these files as the source of truth for adding or editing drugs:

    drugs.json        — Drug rules: enzymes, prodrug status, alternatives
    guidelines.json   — CPIC/DPWG per-phenotype recommendations
    schema.py         — Pydantic models that validate both JSON files
"""
