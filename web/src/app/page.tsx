"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import EvaluationPanel from "@/components/EvaluationPanel";
import AdherencePanel from "@/components/AdherencePanel";
import PathwayVisualizer from "@/components/PathwayVisualizer";
import EvaluationHistory from "@/components/EvaluationHistory";
import Icon from "@/components/Icon";
import MetabolicScene from "@/components/MetabolicScene";
import ErrorBoundary from "@/components/ErrorBoundary";
import type { EvaluationResult, PatientListItem, Medication } from "@/lib/types";
import { EvaluationResultSchema } from "@/lib/schema";

export default function Home() {
  const [patients, setPatients] = useState<PatientListItem[]>([]);
  const [patientsLoading, setPatientsLoading] = useState(true); // CHANGE 3: track patient loading state
  const [patientId, setPatientId] = useState("PGX-001");
  const [medication, setMedication] = useState("Codeine");
  const [allMedications, setAllMedications] = useState<Medication[]>([
    { name: "Codeine", enzyme: "CYP2D6", is_prodrug: true },
    { name: "Tramadol", enzyme: "CYP2D6", is_prodrug: true },
    { name: "Hydrocodone", enzyme: "CYP2D6", is_prodrug: false },
    { name: "Oxycodone", enzyme: "CYP3A4", is_prodrug: false },
    { name: "Clopidogrel", enzyme: "CYP2C19", is_prodrug: true },
    { name: "Pregabalin", enzyme: "—", is_prodrug: false },
    { name: "Duloxetine", enzyme: "CYP2D6", is_prodrug: false },
  ]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EvaluationResult | null>(null);
  const [clinicalNote, setClinicalNote] = useState<string | null>(null);
  const [clinicalNoteDate, setClinicalNoteDate] = useState<string | null>(null);
  const [historyKey, setHistoryKey] = useState(0);
  const [activeIndex, setActiveIndex] = useState(-1);

  useEffect(() => {
    let cancelled = false;

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
          { id: "PGX-001", display_name: "Maria Chen", indication: "Chronic neuropathic pain", phenotype: "Ultra-Rapid Metabolizer" },
          { id: "PGX-002", display_name: "James Okonkwo", indication: "Severe osteoarthritis", phenotype: "Poor Metabolizer" },
          { id: "PGX-003", display_name: "Sarah Patel", indication: "Post-surgical acute pain", phenotype: "Normal Metabolizer" },
        ]);
      })
      .finally(() => {
        if (!cancelled) setPatientsLoading(false); // CHANGE 3: mark loading done
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
  }, []);

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

  // CHANGE 1: Clear results handler
  const handleClearResults = () => {
    setResult(null);
    setClinicalNote(null);
    setClinicalNoteDate(null);
    setError(null);
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
      console.log("Evaluation complete. Result status:", validatedData.status);
    } catch (err: any) {
      console.error("Evaluation Error:", err);
      // Differentiate between Zod schema errors and network errors
      if (err.name === "ZodError") {
        setError("Invalid data received from the clinical agent server.");
      } else {
        setError("Network error. Is the agent server running?");
      }
    } finally {
      setLoading(false);
    }
  }

  const hasWarning =
    result?.flagged === true &&
    (result?.risk_level === "critical" || result?.risk_level === "high");

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
                    riskLevel={result?.risk_level as any}
                  />
                </ErrorBoundary>
                {loading ? (
                  <div className="glass-card rounded-xl p-10 space-y-6 animate-pulse">
                     <div className="h-10 bg-outline-variant/20 rounded w-3/4"></div>
                     <div className="h-4 bg-outline-variant/10 rounded w-full"></div>
                     <div className="h-4 bg-outline-variant/10 rounded w-5/6"></div>
                     <div className="grid grid-cols-3 gap-4 pt-4">
                        <div className="h-20 bg-outline-variant/5 rounded"></div>
                        <div className="h-20 bg-outline-variant/5 rounded"></div>
                        <div className="h-20 bg-outline-variant/5 rounded"></div>
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
                    />
                  </ErrorBoundary>
                ) : (
                  <div className="glass-card rounded-xl border-dashed p-16 text-center text-sm text-on-surface-variant flex flex-col items-center gap-6 bg-surface/30">
                    <div className="w-16 h-16 rounded-full bg-background flex items-center justify-center text-outline/30">
                      <Icon name="biotech" className="h-10 w-10" />
                    </div>
                    <div>
                      <p className="font-bold text-on-surface">System Ready</p>
                      <p className="mt-1 opacity-60">Select a patient profile to begin orchestrated genomic analysis.</p>
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
                      <p className="text-sm text-on-surface-variant mt-1">Live orchestration of specialized clinical intelligence modules. Deterministic logic ensures safe evaluations.</p>
                    </div>
                    {result && (
                      <div className="px-4 py-2 bg-primary/10 rounded-full border border-primary/20 text-[10px] font-bold text-primary uppercase tracking-widest">
                        Status: Execution Finalized
                      </div>
                    )}
                  </div>

                  {result ? (
                    <div className="space-y-0">
                       {result.agent_steps.map((step, idx) => (
                         <div key={idx} className="flex gap-8 relative group">
                           <div className="flex flex-col items-center shrink-0">
                              <div className={`w-10 h-10 rounded-xl flex items-center justify-center z-10 transition-all group-hover:scale-110 ${
                                step.status === 'complete' || step.status === 'approved' ? 'bg-primary text-on-primary shadow-lg shadow-primary/20' :
                                step.status === 'blocked' ? 'bg-error text-on-error' : 'bg-background text-outline border border-outline/20'
                              }`}>
                                <Icon
                                  name={
                                    step.agent === 'Research' ? 'search' :
                                    step.agent === 'Memory' ? 'history' :
                                    step.agent === 'Analyst' ? 'biotech' :
                                    step.agent === 'Critic' ? 'verified_user' :
                                    step.agent === 'Knowledge' ? 'menu_book' :
                                    step.agent === 'Policy' ? 'gavel' :
                                    step.agent === 'Challenge' ? 'report_problem' : 'analytics'
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
                                <h4 className="font-bold text-sm text-on-surface uppercase tracking-widest">{step.agent} Agent</h4>
                                <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase ${
                                  step.status === 'complete' || step.status === 'approved' ? 'bg-primary/10 text-primary' :
                                  step.status === 'blocked' ? 'bg-error/10 text-error' : 'bg-background text-on-surface-variant'
                                }`}>
                                  {step.status}
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
                       ))}
                    </div>
                  ) : (
                    <div className="py-20 text-center text-on-surface-variant">
                       <Icon name="insights" className="mx-auto mb-4 h-12 w-12 opacity-10" />
                       <p className="font-bold">No Active Stream</p>
                       <p className="mt-1 text-xs">Run a prescription evaluation to monitor agent logic in real-time.</p>
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
            <div className="max-w-4xl mx-auto space-y-6">
               <div className="glass-card rounded-xl p-10 min-h-[600px] flex flex-col">
                  <div className="flex items-center justify-between mb-10 border-b border-outline-variant/20 pb-6 shrink-0">
                    <div>
                      <h2 className="text-2xl font-bold text-on-surface">Clinical PGx Documentation</h2>
                      <p className="text-sm text-on-surface-variant mt-1">Formal structured reports for Electronic Health Record (EHR) integration.</p>
                    </div>
                    {clinicalNote && (
                      <button className="bg-primary text-on-primary text-[10px] font-bold uppercase tracking-widest px-4 py-2 rounded shadow-sm hover:bg-primary/90 transition-all flex items-center gap-2">
                        <Icon name="print" className="h-4 w-4" />
                        Print Report
                      </button>
                    )}
                  </div>

                  {clinicalNote ? (
                    <div className="flex-1 bg-surface-container-low/30 rounded-lg p-10 border border-primary/10 shadow-inner overflow-y-auto">
                      <div className="bg-white shadow-xl max-w-2xl mx-auto p-12 border border-outline-variant/30 min-h-[800px]">
                         <div className="border-b-2 border-primary/20 pb-8 mb-8 flex justify-between items-start">
                            <div>
                               <h3 className="text-xl font-bold text-primary uppercase tracking-tighter mb-1">GenomicLens Precision Report</h3>
                               <p className="text-[10px] font-mono text-on-surface-variant">Serial: PGX-DOC-{result?.patient_id}-{result?.medication.toUpperCase()}</p>
                            </div>
                            <div className="text-right text-[10px] font-bold text-on-surface-variant uppercase">
                               Date: {clinicalNoteDate}
                            </div>
                         </div>
                         <pre className="text-sm font-serif text-on-surface leading-relaxed whitespace-pre-wrap">
                            {clinicalNote}
                         </pre>
                         <div className="mt-20 pt-10 border-t border-outline-variant/20 flex justify-between items-end italic text-[10px] text-on-surface-variant/40">
                            <div>Generated by AI Agent: Orchestrator v2.0</div>
                            <div>Confidential Clinical Record</div>
                         </div>
                      </div>
                    </div>
                  ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-on-surface-variant opacity-40">
                       <Icon name="description" className="mb-4 h-14 w-14" />
                       <p className="font-bold">Document Not Finalized</p>
                       <p className="mt-1 text-xs max-w-xs text-center">Generate an EHR note in the Prescription Console to view and finalize the structured report here.</p>
                    </div>
                  )}
               </div>
            </div>
          )}

          {activeTab === "TRIAGE" && (
            <div className="max-w-6xl mx-auto space-y-6">
               <div className="mb-8">
                  <h2 className="text-2xl font-bold text-on-surface">Adherence Triage Center</h2>
                  <p className="text-sm text-on-surface-variant mt-1">Active surveillance of patient outcomes and automated risk assessment.</p>
               </div>

               {/* CHANGE 2: Fixed condition — show AdherencePanel when result is approved, not based on flagged */}
               {result && result.status === "approved" ? (
                 <ErrorBoundary fallbackMessage="Failed to render the adherence triage panel.">
                   <AdherencePanel patientId={result.patient_id} medication={result.medication} />
                 </ErrorBoundary>
               ) : (
                 <div className="glass-card rounded-xl p-20 text-center text-on-surface-variant bg-surface/40">
                    <Icon name="assignment_ind" className="mx-auto mb-4 h-12 w-12 opacity-10" />
                    <p className="font-bold text-on-surface">No Active Surveillance</p>
                    <p className="mt-1 text-xs max-w-sm mx-auto">Adherence monitoring is dynamically enabled after a precision prescription is cleared and dispensed.</p>
                 </div>
               )}
            </div>
          )}
        </div>
      )}
    </AppShell>
  );
}