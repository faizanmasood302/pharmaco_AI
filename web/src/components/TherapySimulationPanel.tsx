"use client";

import { useState } from "react";
import type {
  TherapyCandidate,
  TherapyGenerationResult,
  TherapyValidationCheck,
} from "@/lib/types";
import { TherapyGenerationResultSchema } from "@/lib/schema";
import Icon from "./Icon";

interface TherapySimulationPanelProps {
  patientId: string;
}

function checkLabel(check: TherapyValidationCheck) {
  return check.name.replaceAll("_", " ");
}

function CandidateCard({ candidate }: { candidate: TherapyCandidate }) {
  return (
    <div className="rounded-lg border border-outline-variant/30 bg-surface p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant/60">
            Iteration {candidate.iteration}
          </p>
          <p className="mt-1 text-xs font-bold text-primary">
            {candidate.candidate_id}
          </p>
        </div>
        <span className="rounded-full bg-primary/10 px-3 py-1 text-[9px] font-bold uppercase tracking-widest text-primary">
          {candidate.modality.replaceAll("_", " ")}
        </span>
      </div>
      <p className="mb-4 text-xs leading-relaxed text-on-surface-variant">
        {candidate.rationale}
      </p>
      <div className="rounded bg-background p-3 font-mono text-[11px] leading-relaxed text-on-surface break-all">
        {candidate.sequence}
      </div>
      {candidate.design_constraints.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {candidate.design_constraints.slice(0, 6).map((constraint) => (
            <span
              key={constraint}
              className="rounded border border-outline-variant/30 bg-background px-2 py-1 text-[9px] font-bold uppercase tracking-wider text-on-surface-variant"
            >
              {constraint}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function TherapySimulationPanel({
  patientId,
}: TherapySimulationPanelProps) {
  const [targetDisease, setTargetDisease] = useState("opioid pain response research");
  const [maxIterations, setMaxIterations] = useState(3);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TherapyGenerationResult | null>(null);
  const [decisionLoading, setDecisionLoading] = useState(false);

  async function runSimulation() {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("/api/generate-therapy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_id: patientId,
          target_disease: targetDisease,
          max_iterations: maxIterations,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? data.detail ?? "Research simulation failed");
        return;
      }

      const parsed = TherapyGenerationResultSchema.parse(data);
      setResult(parsed as TherapyGenerationResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Research simulation failed");
    } finally {
      setLoading(false);
    }
  }

  async function submitDecision(decision: "approved" | "rejected") {
    if (!result?.therapy_request_id) return;
    setDecisionLoading(true);
    try {
      const res = await fetch(`/api/therapy-requests/${result.therapy_request_id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          rationale: `Researcher review of n-of-1 simulation for ${targetDisease}.`,
          reviewer: "Clinical Researcher",
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Failed to submit decision");
        return;
      }
      setResult({
        ...result,
        human_gate: {
          ...result.human_gate,
          status: decision,
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Decision submission failed");
    } finally {
      setDecisionLoading(false);
    }
  }

  const validation = result?.validation_result;
  const failedChecks = validation?.checks.filter((check) => !check.passed) ?? [];

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
      <div className="lg:col-span-4 space-y-6">
        <div className="glass-card rounded-xl p-6">
          <label className="mb-3 block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
            Patient Context
          </label>
          <div className="mb-4 rounded-lg border border-outline-variant/30 bg-background px-4 py-3 font-mono text-sm font-bold text-on-surface">
            {patientId}
          </div>

          <label className="mb-3 block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
            Target Disease
          </label>
          <input
            value={targetDisease}
            onChange={(event) => setTargetDisease(event.target.value)}
            className="input-clinical mb-4 w-full rounded-lg bg-surface-container-lowest px-4 py-3 text-sm"
          />

          <label className="mb-3 block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
            Max Iterations
          </label>
          <input
            type="number"
            min={1}
            max={5}
            value={maxIterations}
            onChange={(event) => {
              const value = Number(event.target.value);
              setMaxIterations(Math.max(1, Math.min(5, value || 1)));
            }}
            className="input-clinical mb-6 w-full rounded-lg bg-surface-container-lowest px-4 py-3 text-sm"
          />

          <button
            type="button"
            onClick={runSimulation}
            disabled={loading || !targetDisease.trim()}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-4 text-[11px] font-bold uppercase tracking-widest text-on-primary shadow-md transition-all hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Icon
              name={loading ? "progress_activity" : "science"}
              className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
            />
            {loading ? "Running Simulation..." : "Run Research Simulation"}
          </button>

          {error && (
            <p className="mt-4 rounded border border-error/10 bg-error/5 p-3 text-xs font-bold text-error">
              {error}
            </p>
          )}
        </div>
      </div>

      <div className="lg:col-span-8 space-y-6">
        {!result ? (
          <div className="glass-card flex min-h-[420px] flex-col items-center justify-center gap-5 rounded-xl border-dashed bg-surface/30 p-12 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-background text-outline/30">
              <Icon name="science" className="h-10 w-10" />
            </div>
            <div>
              <p className="font-bold text-on-surface">Research Workspace Ready</p>
              <p className="mt-1 text-xs text-on-surface-variant">
                Select a patient and run a gated n-of-1 simulation.
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="glass-card rounded-xl p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                    Request {result.therapy_request_id?.slice(0, 8) ?? "local"}
                  </p>
                  <h3 className="mt-2 text-2xl font-bold text-on-surface">
                    {result.status.replaceAll("_", " ")}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
                    {result.clinical_narrative}
                  </p>
                </div>
                <div className="rounded-lg border border-primary/15 bg-primary/10 px-4 py-3 text-right">
                  <p className="text-[9px] font-bold uppercase tracking-widest text-primary">
                    Iterations
                  </p>
                  <p className="mt-1 text-2xl font-bold text-primary">
                    {result.iterations}
                  </p>
                </div>
              </div>
            </div>

            {validation && (
              <div className="glass-card rounded-xl p-6">
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-primary">
                      Validation Checks
                    </p>
                    <p className="mt-1 text-sm text-on-surface-variant">
                      Risk score {Math.round(validation.overall_risk_score * 100)}%
                    </p>
                  </div>
                  <span
                    className={`rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-widest ${
                      validation.passed
                        ? "bg-primary/10 text-primary"
                        : "bg-error/10 text-error"
                    }`}
                  >
                    {validation.passed ? "Passed" : "Blocked"}
                  </span>
                </div>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  {validation.checks.map((check) => (
                    <div
                      key={check.name}
                      className="rounded-lg border border-outline-variant/30 bg-background p-4"
                    >
                      <div className="mb-2 flex items-center justify-between gap-3">
                        <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface">
                          {checkLabel(check)}
                        </p>
                        <Icon
                          name={check.passed ? "check_circle" : "report_problem"}
                          className={`h-4 w-4 ${
                            check.passed ? "text-primary" : "text-error"
                          }`}
                        />
                      </div>
                      <p className="text-xs leading-relaxed text-on-surface-variant">
                        {check.detail}
                      </p>
                    </div>
                  ))}
                </div>

                {failedChecks.length > 0 && (
                  <div className="mt-5 rounded-lg border border-error/20 bg-error/5 p-4">
                    <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-error">
                      Failed Checks
                    </p>
                    <ul className="space-y-1">
                      {failedChecks.map((check) => (
                        <li key={check.name} className="text-xs text-on-surface-variant">
                          {checkLabel(check)} requires revision.
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {result.candidate_history.length > 0 && (
              <div className="space-y-4">
                <p className="text-[10px] font-bold uppercase tracking-widest text-primary">
                  Candidate Iterations
                </p>
                {result.candidate_history.map((candidate) => (
                  <CandidateCard key={candidate.candidate_id} candidate={candidate} />
                ))}
              </div>
            )}

            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div className="glass-card rounded-xl p-6">
                <p className="mb-3 text-[10px] font-bold uppercase tracking-widest text-primary">
                  Evidence
                </p>
                <p className="text-sm font-bold text-on-surface">
                  {result.evidence_bundle?.evidence_quality ?? "unknown"} quality
                </p>
                <p className="mt-3 text-xs leading-relaxed text-on-surface-variant">
                  {result.evidence_bundle?.target_rationale}
                </p>
                <p className="mt-4 text-[10px] font-mono text-on-surface-variant/60">
                  {result.evidence_sources.join(", ") || "No source match"}
                </p>
              </div>

              <div className="glass-card rounded-xl p-6">
                <p className="mb-3 text-[10px] font-bold uppercase tracking-widest text-primary">
                  Human Gate
                </p>
                <p className="text-sm font-bold uppercase tracking-wider text-on-surface">
                  {result.human_gate.status.replaceAll("_", " ")}
                </p>
                <p className="mt-3 text-xs leading-relaxed text-on-surface-variant">
                  {result.human_gate.reason}
                </p>
                {result.human_gate.status === "pending" && (
                  <div className="mt-6 grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      disabled={decisionLoading}
                      onClick={() => submitDecision("approved")}
                      className="flex items-center justify-center gap-2 rounded bg-primary py-2 text-[10px] font-bold uppercase tracking-widest text-on-primary shadow transition-all hover:bg-primary/90 disabled:opacity-50"
                    >
                      <Icon name="check" className="h-3.5 w-3.5" />
                      Approve Simulation
                    </button>
                    <button
                      type="button"
                      disabled={decisionLoading}
                      onClick={() => submitDecision("rejected")}
                      className="flex items-center justify-center gap-2 rounded bg-error/10 py-2 text-[10px] font-bold uppercase tracking-widest text-error transition-all hover:bg-error/20 disabled:opacity-50"
                    >
                      <Icon name="close" className="h-3.5 w-3.5" />
                      Reject
                    </button>
                  </div>
                )}
                {result.human_gate.required_fields.length > 0 && result.human_gate.status === "pending" && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {result.human_gate.required_fields.map((field) => (
                      <span
                        key={field}
                        className="rounded border border-outline-variant/30 bg-background px-2 py-1 text-[9px] font-bold uppercase tracking-wider text-on-surface-variant"
                      >
                        {field.replaceAll("_", " ")}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
