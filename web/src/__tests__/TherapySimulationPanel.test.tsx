import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import "@testing-library/jest-dom";
import React from "react";
import TherapySimulationPanel from "../components/TherapySimulationPanel";
import type { TherapyGenerationResult } from "../lib/types";

function jsonResponse(body: unknown, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(body),
  } as Response);
}

const therapyResult: TherapyGenerationResult = {
  status: "research_review_required",
  patient_id: "PGX-001",
  target_disease: "opioid pain response research",
  mrna_sequence: "AUGGCUUAA",
  toxicity_score: 0.42,
  iterations: 2,
  agent_steps: [],
  clinical_narrative: "Candidate package is ready for human research review.",
  therapy_request_id: "therapy-req-1",
  candidate_id: "therapy-cand-1",
  final_candidate: {
    candidate_id: "therapy-cand-1",
    iteration: 2,
    modality: "simulated_mrna",
    sequence: "AUGGCUUAA",
    design_constraints: ["research simulation only", "human review required"],
    rationale: "Generated from source-backed context.",
    evidence_refs: ["n_of_1_research_simulation_policy.md"],
  },
  candidate_history: [
    {
      candidate_id: "therapy-cand-0",
      iteration: 1,
      modality: "simulated_mrna",
      sequence: "AUGGCUUAG",
      design_constraints: ["research simulation only"],
      rationale: "Initial candidate.",
      evidence_refs: ["n_of_1_research_simulation_policy.md"],
    },
    {
      candidate_id: "therapy-cand-1",
      iteration: 2,
      modality: "simulated_mrna",
      sequence: "AUGGCUUAA",
      design_constraints: ["research simulation only", "human review required"],
      rationale: "Revised candidate.",
      evidence_refs: ["n_of_1_research_simulation_policy.md"],
    },
  ],
  validation_result: {
    passed: false,
    overall_risk_score: 0.72,
    checks: [
      {
        name: "rna_alphabet",
        passed: true,
        score: 1,
        detail: "Sequence uses only A, U, G, and C.",
        severity: "critical",
      },
      {
        name: "internal_stop_codons",
        passed: false,
        score: 0,
        detail: "Detected 1 internal stop codons.",
        severity: "critical",
      },
    ],
    blocked_reasons: ["Detected 1 internal stop codons."],
    revision_hints: ["Remove internal stop codons from the coding region."],
  },
  evidence_bundle: {
    sources: ["n_of_1_research_simulation_policy.md"],
    target_rationale: "Retrieved source chunks for research simulation.",
    known_risks: ["The candidate is not clinically validated."],
    open_questions: ["What external bioinformatics tools are required next?"],
    evidence_quality: "moderate",
    source_snippets: [],
  },
  evidence_sources: ["n_of_1_research_simulation_policy.md"],
  safety_notes: ["Research simulation only."],
  audit_trail: [
    {
      stage: "human_gate",
      decision: "pending",
      rationale: "Research review required.",
      requires_human_review: true,
    },
  ],
  logic_tree: null,
  human_gate: {
    required: true,
    status: "pending",
    reason: "Researcher or clinician review required before downstream use.",
    required_fields: ["reviewer_id"],
  },
};

describe("TherapySimulationPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn(() => jsonResponse(therapyResult)) as typeof fetch;
  });

  it("runs a therapy simulation and renders iterations and failed checks", async () => {
    render(<TherapySimulationPanel patientId="PGX-001" />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Run Research Simulation/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/research review required/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Candidate Iterations/i)).toBeInTheDocument();
    expect(screen.getByText(/therapy-cand-0/i)).toBeInTheDocument();
    expect(screen.getByText(/Validation Checks/i)).toBeInTheDocument();
    expect(screen.getByText(/Detected 1 internal stop codons/i)).toBeInTheDocument();
    expect(screen.getByText(/Human Gate/i)).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/generate-therapy",
      expect.objectContaining({
        method: "POST",
      })
    );
  });
});
