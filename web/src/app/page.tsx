"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import EvaluationPanel from "@/components/EvaluationPanel";
import AdherencePanel from "@/components/AdherencePanel";
import PathwayVisualizer from "@/components/PathwayVisualizer";
import EvaluationHistory from "@/components/EvaluationHistory";
import TherapySimulationPanel from "@/components/TherapySimulationPanel";
import ReviewFlowPanel from "@/components/ReviewFlowPanel";
import Icon from "@/components/Icon";
import MetabolicScene from "@/components/MetabolicScene";
import ErrorBoundary from "@/components/ErrorBoundary";
import { useToast } from "@/components/Toast";
import type {
  ClinicalReport,
  EvaluationResult,
  Medication,
  PatientListItem,
} from "@/lib/types";
import { EvaluationResultSchema } from "@/lib/schema";
import { authClient } from "@/lib/auth-client";

function getErrorMessage(err: unknown, fallback: string) {
  return err instanceof Error ? err.message : fallback;
}

function normalizeRiskLevel(level?: string): "optimal" | "elevated" | "critical" {
  const risk = (level ?? "").toLowerCase();
  if (risk === "critical") return "critical";
  if (risk === "high" || risk === "moderate" || risk === "elevated") return "elevated";
  return "optimal";
}

export default function Home() {
  const router = useRouter();
  const [patients, setPatients] = useState<PatientListItem[]>([]);
  const [patientsLoading, setPatientsLoading] = useState(true);
  const [isAuthenticating, setIsAuthenticating] = useState(true);
  const [patientId, setPatientId] = useState("PGX-001");
  const [medication, setMedication] = useState("Codeine");
  const [allMedications, setAllMedications] = useState<Medication[]>([
    { name: "Codeine", enzyme: "CYP2D6", is_prodrug: true },
    { name: "Tramadol", enzyme: "CYP2D6", is_prodrug: true },
    { name: "Hydrocodone", enzyme: "CYP2D6", is_prodrug: false },
    { name: "Oxycodone", enzyme: "CYP3A4", is_prodrug: false },
    { name: "Clopidogrel", enzyme: "CYP2C19", is_prodrug: true },
    { name: "Pregabalin", enzyme: "\u2014", is_prodrug: false },
    { name: "Duloxetine", enzyme: "CYP2D6", is_prodrug: false },
    { name: "Citalopram", enzyme: "CYP2C19", is_prodrug: false },
    { name: "Escitalopram", enzyme: "CYP2C19", is_prodrug: false },
    { name: "Sertraline", enzyme: "CYP2C19", is_prodrug: false },
    { name: "Paroxetine", enzyme: "CYP2D6", is_prodrug: false },
    { name: "Prasugrel", enzyme: "CYP3A4", is_prodrug: true },
    { name: "Ticagrelor", enzyme: "\u2014", is_prodrug: false },
    { name: "Acetaminophen", enzyme: "\u2014", is_prodrug: false },
  ]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EvaluationResult | null>(null);
  const [clinicalNote, setClinicalNote] = useState<string | null>(null);
  const [clinicalNoteDate, setClinicalNoteDate] = useState<string | null>(null);
  const [historyKey, setHistoryKey] = useState(0);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [patientReports, setPatientReports] = useState<ClinicalReport[]>([]);
  const [reportsLoading, setPatientReportsLoading] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    if (!patientId) return;

    async function fetchReports() {
      setPatientReportsLoading(true);
      try {
        const res = await fetch(`/api/patients/${patientId}/reports`);
        const data = await res.json();
        if (res.ok) {
          setPatientReports(data.reports || []);
        }
      } catch (err) {
        console.error("Failed to fetch reports:", err);
      } finally {
        setPatientReportsLoading(false);
      }
    }

    fetchReports();
  }, [patientId, historyKey]);

  // Authentication guard
  useEffect(() => {
    let cancelled = false;

    const checkAuthentication = async () => {
      try {
        const session = await authClient.getSession();
        if (cancelled) return;

        if (!session || !session.data) {
          router.push("/login");
          return;
        }

        setIsAuthenticating(false);
      } catch (err) {
        if (cancelled) return;
        console.error("Auth check failed:", err);
        router.push("/login");
      }
    };

    checkAuthentication();

    return () => {
      cancelled = true;
    };
  }, [router]);

  useEffect(() => {
    let cancelled = false;

    if (isAuthenticating) return;

    // Fetch patients
    fetch("/api/patients")
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return;
        if (data.patients?.length) {
          setPatients(data.patients);
          setPatientId((current) =>
            data.patients.some((p: PatientListItem) => p.id === current)
              ? current
              : data.patients[0].id
          );
        }
      })
      .catch(() => {
        if (cancelled) return;
        setPatients([
          { id: "PGX-004", display_name: "Alex Rivera", indication: "Severe acute pain post-injury", phenotype: "Ultra-Rapid Metabolizer" },
          { id: "PGX-001", display_name: "Maria Chen", indication: "Chronic neuropathic pain", phenotype: "Ultra-Rapid Metabolizer" },
          { id: "PGX-002", display_name: "James Okonkwo", indication: "Severe osteoarthritis", phenotype: "Poor Metabolizer" },
          { id: "PGX-003", display_name: "Sarah Patel", indication: "Post-surgical acute pain", phenotype: "Normal Metabolizer" },
        ]);
      })
      .finally(() => {
        if (!cancelled) setPatientsLoading(false);
      });

    // Fetch medications for autocomplete
    fetch("/api/medications")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch medications");
        return res.json();
      })
      .then((data) => {
        if (cancelled) return;
        if (data.medications?.length) {
          setAllMedications(data.medications);
        }
      })
      .catch((err) => {
        console.warn("Using default medication list:", err);
      });

    return () => {
      cancelled = true;
    };
  }, [isAuthenticating]);

  const filteredMedications = allMedications.filter(m => {
    const search = medication.toLowerCase().trim();
    if (!search) return true;
    return m.name.toLowerCase().includes(search) ||
           m.enzyme.toLowerCase().includes(search);
  });

  const handleSelectMedication = (name: string) => {
    setMedication(name);
    setShowSuggestions(false);
    setActiveIndex(-1);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showSuggestions) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex(prev => (prev + 1) % filteredMedications.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex(prev => (prev - 1 + filteredMedications.length) % filteredMedications.length);
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      handleSelectMedication(filteredMedications[activeIndex].name);
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
      setActiveIndex(-1);
    }
  };

  const handleClearResults = () => {
    setResult(null);
    setClinicalNote(null);
    setClinicalNoteDate(null);
    setError(null);
    toast("Results cleared", "info");
  };

  async function handleEvaluate() {
    setLoading(true);
    setError(null);
    setResult(null);
    setClinicalNote(null);
    setClinicalNoteDate(null);

    try {
      const res = await fetch("/api/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patient_id: patientId, medication }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Evaluation failed");
        return;
      }
      // Safe parsing using Zod to enforce schema contract
      const validatedData = EvaluationResultSchema.parse(data);
      setResult(validatedData as EvaluationResult);
      setHistoryKey((k) => k + 1);
      toast("Evaluation complete — review results below", "success");
    } catch (err: unknown) {
      console.error("Evaluation Error:", err);
      // Differentiate between Zod schema errors and network errors
      if (err instanceof Error && err.name === "ZodError") {
        setError("Invalid data received from the clinical agent server.");
        toast("Invalid data from agent server", "error");
      } else {
        setError("Network error. Is the agent server running?");
        toast("Agent server unreachable", "error");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleReviewDecision(decision: "approved" | "rejected", rationale: string) {
    const id = result?.evaluation_id;
    
    if (!id) {
      setError("Critical Error: Evaluation session expired or ID missing. Please re-run the evaluation.");
      return false;
    }

    try {
      const res = await fetch(`/api/evaluations/${id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          rationale: rationale || null,
        }),
      });
      
      const data = await res.json();

      if (!res.ok) {
        setError(data.error ?? data.detail ?? "Review update failed");
        return false;
      }

      // Backend returns { evaluation: result_json } or similar
      const updatedResult = data.evaluation ?? data;
      const validatedData = EvaluationResultSchema.parse(updatedResult);
      
      setResult(validatedData as EvaluationResult);
      setHistoryKey((k) => k + 1);
      setError(null);
      toast(`Decision recorded: ${decision}`, decision === "approved" ? "success" : "info");
      return true;
    } catch (err: unknown) {
      console.error("Review decision error:", err);
      setError(getErrorMessage(err, "Unable to save review decision."));
      return false;
    }
  }

  const hasWarning =
    result?.flagged === true &&
    (result?.risk_level === "critical" || result?.risk_level === "high");
  const humanGateStatus = result?.human_gate?.status;
  const adherenceApproved = humanGateStatus === "approved";
  const humanGateLabel = humanGateStatus ? humanGateStatus.replaceAll("_", " ") : "pending";

  if (isAuthenticating) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-5 animate-fade-in-up">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20">
            <Icon name="biotech" className="h-7 w-7 text-primary" />
          </div>
          <Icon name="progress_activity" className="h-6 w-6 animate-spin text-primary" />
          <p className="text-on-surface-variant text-sm font-medium">Verifying credentials...</p>
        </div>
      </div>
    );
  }

  return (
    <AppShell>
      {(activeTab) => (
        <div className="animate-in fade-in duration-500">
          {activeTab === "PRESCRIPTION" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              <div className="lg:col-span-4 space-y-6">
                 <div className="glass-card rounded-xl p-6">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-3 block">Active Target</label>
                    <div className="relative mb-4">
                      {/* CHANGE 3: Show spinner while patients are loading */}
                      {patientsLoading ? (
                        <div className="input-clinical w-full bg-surface-container-lowest rounded-lg py-3 px-4 flex items-center gap-2 text-on-surface-variant/50 text-sm">
                          <Icon name="progress_activity" className="h-4 w-4 animate-spin" />
                          Loading patients...
                        </div>
                      ) : (
                        <>
                          <select
                            value={patientId}
                            onChange={(e) => setPatientId(e.target.value)}
                            className="input-clinical w-full bg-surface-container-lowest font-sans text-sm rounded-lg py-3 px-4 appearance-none cursor-pointer pr-10"
                            disabled={loading}
                          >
                            {patients.map((p) => (
                              <option key={p.id} value={p.id}>{p.display_name} — {p.phenotype}</option>
                            ))}
                          </select>
                          <Icon name="expand_more" className="absolute right-3 top-1/2 h-5 w-5 -translate-y-1/2 text-outline pointer-events-none" />
                        </>
                      )}
                    </div>

                    <label className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-3 block">Proposed Therapy</label>
                    <div className="relative mb-6">
                       <Icon name="search" className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-primary z-10" />
                       <input
                         value={medication}
                         onChange={(e) => {
                            setMedication(e.target.value);
                            setShowSuggestions(true);
                            setActiveIndex(-1);
                         }}
                         onFocus={() => {
                           setShowSuggestions(true);
                           setActiveIndex(-1);
                         }}
                         onKeyDown={handleKeyDown}
                         onBlur={() => setTimeout(() => {
                           setShowSuggestions(false);
                           setActiveIndex(-1);
                         }, 200)}
                         className="input-clinical w-full bg-surface-container-lowest font-mono text-sm rounded-lg py-3 pl-12 pr-10"
                         placeholder="Scan drug database..."
                       />
                       {medication && (
                         <button
                           onClick={() => setMedication("")}
                           className="absolute right-3 top-1/2 -translate-y-1/2 text-outline-variant hover:text-primary transition-colors"
                         >
                           <Icon name="close" className="h-4 w-4" />
                         </button>
                       )}

                       {showSuggestions && (
                         <div className="absolute top-full left-0 w-full mt-1 bg-surface-container-lowest border border-outline-variant/30 rounded-lg shadow-xl z-50 max-h-48 overflow-y-auto animate-in fade-in slide-in-from-top-2 duration-200">
                            {filteredMedications.map((m, idx) => (
                                <button
                                  key={m.name}
                                  onPointerDown={(e) => {
                                    e.preventDefault();
                                    handleSelectMedication(m.name);
                                  }}
                                  onMouseEnter={() => setActiveIndex(idx)}
                                  className={`w-full text-left px-4 py-3 border-b border-outline-variant/10 last:border-0 flex items-center justify-between group transition-colors ${
                                    idx === activeIndex ? "bg-primary/10" : "hover:bg-primary/5"
                                  }`}
                                >
                                  <div>
                                    <span className={`text-sm font-bold transition-colors ${idx === activeIndex ? "text-primary" : "text-on-surface"} group-hover:text-primary`}>{m.name}</span>
                                    <span className="ml-2 text-[10px] font-mono text-on-surface-variant/60">{m.enzyme}</span>
                                  </div>
                                  {m.is_prodrug && (
                                    <span className={`text-[8px] font-bold uppercase tracking-tighter px-1.5 py-0.5 rounded ${
                                      idx === activeIndex ? "bg-primary/20 text-primary" : "bg-secondary/10 text-secondary"
                                    }`}>Prodrug</span>
                                  )}
                                </button>
                              ))
                            }
                            {filteredMedications.length === 0 && (
                                <div className="px-4 py-3 text-xs text-on-surface-variant/60 italic">No exact clinical match found</div>
                              )
                            }
                         </div>
                       )}
                    </div>

                    <button
                      onClick={handleEvaluate}
                      disabled={loading || !medication.trim()}
                      className="w-full bg-primary text-on-primary text-[11px] font-bold uppercase tracking-widest py-4 rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md flex items-center justify-center gap-2 active:scale-95"
                    >
                      {loading ? (
                        <>
                          <Icon name="progress_activity" className="h-4 w-4 animate-spin" />
                          Analyzing Multi-Agent Pipeline...
                        </>
                      ) : (
                        <>
                          <Icon name="analytics" className="h-4 w-4" />
                          Run Precision Evaluation
                        </>
                      )}
                    </button>

                    {/* CHANGE 1: Clear Results button */}
                    {result && (
                      <button
                        onClick={handleClearResults}
                        className="w-full mt-2 text-[11px] font-bold uppercase tracking-widest py-3 rounded-lg border border-outline-variant/30 text-on-surface-variant hover:bg-surface-container transition-all flex items-center justify-center gap-2 active:scale-95"
                      >
                        <Icon name="close" className="h-4 w-4" />
                        Clear Results
                      </button>
                    )}

                    {error && <p className="mt-4 text-xs text-error font-bold bg-error/5 p-3 rounded border border-error/10">{error}</p>}
                 </div>

                 <EvaluationHistory patientId={patientId} refreshKey={historyKey} />
              </div>

              <div className="lg:col-span-8 space-y-6">
                <ErrorBoundary fallbackMessage="Failed to render the 3D metabolic scene.">
                  <MetabolicScene
                    hasWarning={hasWarning}
                    riskLevel={normalizeRiskLevel(result?.risk_level)}
                  />
                </ErrorBoundary>
                {loading ? (
                  <div className="glass-card rounded-xl p-10 space-y-6 animate-fade-in-up">
                     <div className="flex items-center gap-3 mb-2">
                       <Icon name="progress_activity" className="h-5 w-5 animate-spin text-primary" />
                       <span className="text-[10px] font-bold uppercase tracking-widest text-primary">Analyzing</span>
                     </div>
                     <div className="h-10 bg-gradient-to-r from-outline-variant/20 via-outline-variant/10 to-outline-variant/20 rounded animate-pulse w-3/4"></div>
                     <div className="h-4 bg-gradient-to-r from-outline-variant/10 via-outline-variant/5 to-outline-variant/10 rounded animate-pulse w-full"></div>
                     <div className="h-4 bg-gradient-to-r from-outline-variant/10 via-outline-variant/5 to-outline-variant/10 rounded animate-pulse w-5/6"></div>
                     <div className="grid grid-cols-3 gap-4 pt-4">
                        <div className="h-20 bg-gradient-to-b from-outline-variant/10 to-outline-variant/5 rounded animate-pulse"></div>
                        <div className="h-20 bg-gradient-to-b from-outline-variant/10 to-outline-variant/5 rounded animate-pulse"></div>
                        <div className="h-20 bg-gradient-to-b from-outline-variant/10 to-outline-variant/5 rounded animate-pulse"></div>
                     </div>
                  </div>
                ) : result ? (
                  <ErrorBoundary fallbackMessage="Failed to render the clinical evaluation panel.">
                    <EvaluationPanel
                      result={result}
                      onNoteGenerated={(note) => {
                        setClinicalNote(note);
                        setClinicalNoteDate(new Date().toLocaleDateString());
                      }}
                      onReviewDecision={handleReviewDecision}
                    />
                  </ErrorBoundary>
                ) : (
                  <div className="glass-card rounded-xl border-dashed p-16 text-center text-sm text-on-surface-variant flex flex-col items-center gap-6 bg-surface/30 animate-fade-in-up">
                    <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary/5 to-secondary/5 flex items-center justify-center border border-primary/10">
                      <Icon name="biotech" className="h-10 w-10 text-primary/40" />
                    </div>
                    <div className="max-w-sm">
                      <p className="font-bold text-on-surface text-base">System Ready</p>
                      <p className="mt-2 text-sm text-on-surface-variant/60 leading-relaxed">
                        Select a patient profile and proposed therapy, then run a precision evaluation to initiate the multi-agent pipeline.
                      </p>
                    </div>
                    <div className="flex items-center gap-6 pt-2">
                      <div className="flex items-center gap-2 text-[10px] font-bold text-on-surface-variant/40 uppercase tracking-widest">
                        <Icon name="check_circle" className="h-3.5 w-3.5 text-primary/50" />
                        Pipeline Ready
                      </div>
                      <div className="flex items-center gap-2 text-[10px] font-bold text-on-surface-variant/40 uppercase tracking-widest">
                        <Icon name="check_circle" className="h-3.5 w-3.5 text-primary/50" />
                        Human Gate Active
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "PIPELINE" && (
            <div className="max-w-4xl mx-auto space-y-6">
               <div className="glass-card rounded-xl p-10">
                  <div className="flex items-center justify-between mb-10 border-b border-outline-variant/20 pb-6">
                    <div>
                      <h2 className="text-2xl font-bold text-on-surface">Agent Execution Stream</h2>
                      <p className="text-sm text-on-surface-variant mt-1">Prototype orchestration of specialized research simulation modules. Retrieval, reasoning, critique, and reporting are followed by an explicit human review gate.</p>
                    </div>
                    {result && (
                      <div className="px-4 py-2 bg-primary/10 rounded-full border border-primary/20 text-[10px] font-bold text-primary uppercase tracking-widest">
                        Human gate: {humanGateLabel}
                      </div>
                    )}
                  </div>

                  {result ? (
                    <div className="space-y-0">
                      {result.agent_steps.map((step, idx) => {
                        const displayStatus =
                          step.agent === "HumanGate" ? humanGateStatus ?? step.status : step.status;

                        return (
                          <div key={idx} className="flex gap-8 relative group">
                            <div className="flex flex-col items-center shrink-0">
                              <div className={`w-10 h-10 rounded-xl flex items-center justify-center z-10 transition-all group-hover:scale-110 ${
                                displayStatus === "complete" || displayStatus === "approved" ? "bg-primary text-on-primary shadow-lg shadow-primary/20" :
                                displayStatus === "blocked" || displayStatus === "rejected" ? "bg-error text-on-error" : "bg-background text-outline border border-outline/20"
                              }`}>
                                <Icon
                                  name={
                                    step.agent === "Retrieval" || step.agent === "Research" ? "search" :
                                    step.agent === "Reasoning" || step.agent === "Analyst" ? "psychology" :
                                    step.agent === "Critic" ? "verified_user" :
                                    step.agent === "Knowledge" ? "menu_book" :
                                    step.agent === "Policy" ? "gavel" :
                                    step.agent === "Reporter" ? "description" :
                                    step.agent === "HumanGate" ? "fact_check" :
                                    step.agent === "Challenge" ? "report_problem" :
                                    step.agent === "Orchestrator" ? "hub" : "analytics"
                                  }
                                  className="h-5 w-5"
                                />
                              </div>
                              {idx < result.agent_steps.length - 1 && (
                                <div className="w-0.5 flex-1 bg-outline-variant/30 my-2" />
                              )}
                            </div>
                            <div className="pb-12 pt-1 flex-1">
                              <div className="flex items-center gap-3 mb-2">
                                <h4 className="font-bold text-sm text-on-surface uppercase tracking-widest">
                                  {step.agent === "HumanGate" ? "Human Gate" : step.agent} Agent
                                </h4>
                                <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase ${
                                  displayStatus === "complete" || displayStatus === "approved" ? "bg-primary/10 text-primary" :
                                  displayStatus === "blocked" || displayStatus === "rejected" ? "bg-error/10 text-error" : "bg-background text-on-surface-variant"
                                }`}>
                                  {displayStatus}
                                </span>
                              </div>
                              <p className="text-sm text-on-surface-variant leading-relaxed bg-background/50 p-4 rounded-lg border border-outline-variant/10">
                                {step.summary}
                              </p>
                              {step.duration_ms != null && (
                                <div className="flex items-center gap-2 mt-3 text-[10px] font-mono text-on-surface-variant/40">
                                  <Icon name="timer" className="h-3 w-3" />
                                  Latent Execution: {step.duration_ms}ms
                                  {typeof step.confidence === "number" && (
                                    <span>Confidence: {Math.round(step.confidence * 100)}%</span>
                                  )}
                                </div>
                              )}
                              {step.evidence_refs && step.evidence_refs.length > 0 && (
                                <div className="mt-2 text-[10px] font-mono text-on-surface-variant/50">
                                  Evidence: {step.evidence_refs.join(", ")}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="py-20 text-center text-on-surface-variant">
                       <Icon name="insights" className="mx-auto mb-4 h-12 w-12 opacity-10" />
                       <p className="font-bold">No Active Stream</p>
                       <p className="mt-1 text-xs">Run a prescription evaluation to inspect the agent logic trace.</p>
                    </div>
                  )}
               </div>
            </div>
          )}

          {activeTab === "PATHWAY" && (
            <div className="max-w-5xl mx-auto space-y-6">
               <div className="glass-card rounded-xl p-10">
                  <div className="mb-10">
                    <h2 className="text-2xl font-bold text-on-surface">Metabolic Pathway Mapping</h2>
                    <p className="text-sm text-on-surface-variant mt-1">Biochemical conversion schematic based on patient-specific enzymatic activity.</p>
                  </div>
                  {result ? (
                    <ErrorBoundary fallbackMessage="Failed to render pathway visualization.">
                      <PathwayVisualizer result={result} />
                    </ErrorBoundary>
                  ) : (
                    <div className="py-20 text-center text-on-surface-variant border-2 border-dashed border-outline-variant/20 rounded-xl">
                       <p className="font-bold">Awaiting Genomic Data</p>
                       <p className="mt-1 text-xs">Biochemical mapping requires an active prescription evaluation result.</p>
                    </div>
                  )}
               </div>
            </div>
          )}

          {activeTab === "REPORTS" && (
            <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
               <div className="lg:col-span-4 space-y-6">
                 <div className="glass-card rounded-xl p-6">
                    <h3 className="text-[10px] font-bold uppercase tracking-widest text-primary mb-4">Report Archive</h3>
                    {reportsLoading ? (
                      <div className="py-10 text-center animate-pulse">
                         <Icon name="progress_activity" className="h-6 w-6 animate-spin mx-auto text-outline/30" />
                      </div>
                    ) : patientReports.length > 0 ? (
                      <div className="space-y-2">
                        {patientReports.map((report) => (
                          <button
                            key={report.id}
                            onClick={() => {
                              setClinicalNote(report.content);
                              setClinicalNoteDate(new Date(report.created_at).toLocaleDateString());
                            }}
                            className={`w-full text-left p-3 rounded-lg border transition-all ${
                              clinicalNote === report.content 
                                ? "bg-primary/10 border-primary/30" 
                                : "bg-surface-container-lowest border-outline-variant/20 hover:border-primary/20"
                            }`}
                          >
                            <div className="flex justify-between items-start">
                              <span className="text-xs font-bold text-on-surface">Draft Report</span>
                              <span className="text-[9px] font-mono text-on-surface-variant/40">
                                {new Date(report.created_at).toLocaleDateString()}
                              </span>
                            </div>
                            <p className="mt-1 text-[10px] text-on-surface-variant truncate">
                              ID: {report.id.slice(0, 8)}...
                            </p>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <div className="py-10 text-center text-on-surface-variant/50 italic text-xs">
                        No saved clinical reports found for this patient.
                      </div>
                    )}
                 </div>
               </div>

               <div className="lg:col-span-8">
                 <div className="glass-card rounded-xl p-10 min-h-[600px] flex flex-col">
                    <div className="flex items-center justify-between mb-10 border-b border-outline-variant/20 pb-6 shrink-0">
                      <div>
                        <h2 className="text-2xl font-bold text-on-surface">Clinical PGx Documentation</h2>
                        <p className="text-sm text-on-surface-variant mt-1">Prototype structured reports for simulated review workflows.</p>
                      </div>
                      {clinicalNote && (
                        <button
                          onClick={() => window.print()}
                          className="bg-primary text-on-primary text-[10px] font-bold uppercase tracking-widest px-4 py-2 rounded shadow-sm hover:bg-primary/90 transition-all flex items-center gap-2 active:scale-95"
                        >
                          <Icon name="print" className="h-4 w-4" />
                          Print Report
                        </button>
                      )}
                    </div>

                    {clinicalNote ? (
                      <div className="print-content flex-1 bg-surface-container-low/30 rounded-lg p-10 border border-primary/10 shadow-inner overflow-y-auto">
                        <div className="bg-white shadow-xl max-w-2xl mx-auto p-12 border border-outline-variant/30 min-h-[800px] relative">
                           <div className="absolute top-4 right-4 print:hidden">
                              <button onClick={() => setClinicalNote(null)} className="text-on-surface-variant/30 hover:text-primary transition-colors">
                                <Icon name="close" className="h-5 w-5" />
                              </button>
                           </div>
                           <div className="border-b-2 border-primary/20 pb-8 mb-8 flex justify-between items-start">
                              <div>
                                 <h3 className="text-xl font-bold text-primary uppercase tracking-tighter mb-1">GenomicLens Precision Report</h3>
                                 <p className="text-[10px] font-mono text-on-surface-variant">Structured Agentic Output</p>
                              </div>
                              <div className="text-right text-[10px] font-bold text-on-surface-variant uppercase">
                                 Date: {clinicalNoteDate}
                              </div>
                           </div>
                           <pre className="text-sm font-serif text-on-surface leading-relaxed whitespace-pre-wrap">
                              {clinicalNote}
                           </pre>
                           <div className="mt-20 pt-10 border-t border-outline-variant/20 flex justify-between items-end italic text-[10px] text-on-surface-variant/40">
                              <div>Generated by research simulation orchestrator</div>
                              <div>Synthetic demo record - not for clinical use</div>
                           </div>
                        </div>
                      </div>
                    ) : (
                      <div className="flex-1 flex flex-col items-center justify-center text-on-surface-variant opacity-40">
                         <Icon name="description" className="mb-4 h-14 w-14" />
                         <p className="font-bold">Document Not Finalized</p>
                         <p className="mt-1 text-xs max-w-xs text-center">Generate a draft note in the Prescription Console to review the structured report here.</p>
                      </div>
                    )}
                 </div>
               </div>
            </div>
          )}

          {activeTab === "TRIAGE" && (
            <div className="max-w-6xl mx-auto space-y-6">
               <div className="mb-8">
                  <h2 className="text-2xl font-bold text-on-surface">Adherence Triage Center</h2>
                  <p className="text-sm text-on-surface-variant mt-1">Simulated adherence follow-up and deterministic risk triage for prototype review.</p>
               </div>

               {result && adherenceApproved ? (
                 <ErrorBoundary fallbackMessage="Failed to render the adherence triage panel.">
                   <AdherencePanel patientId={result.patient_id} medication={result.medication} />
                 </ErrorBoundary>
               ) : (
                 <div className="glass-card rounded-xl p-20 text-center text-on-surface-variant bg-surface/40">
                    <Icon name="assignment_ind" className="mx-auto mb-4 h-12 w-12 opacity-10" />
                    <p className="font-bold text-on-surface">
                      {humanGateStatus === "rejected" ? "Clinician Rejected" : "Awaiting Clinician Approval"}
                    </p>
                    <p className="mt-1 text-xs max-w-sm mx-auto">
                      {humanGateStatus === "rejected"
                        ? "The prescription was not cleared, so adherence monitoring remains disabled."
                        : "Adherence monitoring is dynamically enabled after a precision prescription passes human review and is dispensed."}
                    </p>
                 </div>
               )}
            </div>
          )}

          {activeTab === "REVIEW_FLOW" && (
            <ReviewFlowPanel result={result} />
          )}

          {activeTab === "RESEARCH" && (
            <div className="max-w-7xl mx-auto space-y-6">
              <div className="mb-8">
                <h2 className="text-2xl font-bold text-on-surface">N-of-1 Research Simulation</h2>
                <p className="text-sm text-on-surface-variant mt-1">Source-grounded candidate design, deterministic validation, and human research review.</p>
              </div>
              <ErrorBoundary fallbackMessage="Failed to render the n-of-1 research simulation.">
                <TherapySimulationPanel patientId={patientId} />
              </ErrorBoundary>
            </div>
          )}
        </div>
      )}
    </AppShell>
  );
}
