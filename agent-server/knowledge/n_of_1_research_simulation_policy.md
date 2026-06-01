# N-of-1 Therapy Research Simulation Policy

This source defines the local evidence and safety policy for simulated n-of-1 therapy generation in GenomicLens.

## Scope

The n-of-1 therapy workflow is a research simulation. It may produce a constrained candidate sequence, validation report, audit trail, and review packet. It must not represent the candidate as a clinically approved treatment, a dosing instruction, or a manufacturing-ready product.

## Target Selection

A candidate target must be tied to patient context and disease rationale. If disease-specific evidence is missing, the workflow should record the uncertainty and require human research review before downstream use.

## Candidate Design

Simulated mRNA candidates must use RNA alphabet characters only, begin with a start codon, preserve codon frame, avoid internal stop codons, and end with a terminal stop codon. The design agent must report constraints and unresolved assumptions.

## Validation Rules

The validation suite should produce deterministic checks for sequence syntax, start codon, terminal stop codon, frame length, internal stop codons, GC content, repeated motifs, and simple immunogenic motif risk. Failed checks must produce revision hints.

## Human Review

Every generated candidate requires researcher or clinician review. Required review fields include reviewer identity, research rationale, evidence review attestation, and safety risk acknowledgement.
