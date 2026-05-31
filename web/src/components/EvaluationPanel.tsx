"use client";

import { useState } from "react";
import type { EvaluationResult } from "@/lib/types";
import Icon from "./Icon";
import PictogramStrip from "./PictogramStrip";

const RISK_STYLES: Record<string, string> = {
  none: "pill-normal",
  low: "pill-normal",
  moderate: "bg-amber-100 text-amber-800 border-amber-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  critical: "pill-poor",
};

interface EvaluationPanelProps {
  result: EvaluationResult;
  onNoteGenerated?: (note: string) => void;
}

function LogicTreeNode({ node }: { node: any }) {
  return (
    <div className="ml-4 border-l border-outline-variant/30 pl-4 py-2">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${node.flag ? 'bg-error' : 'bg-primary'}`} />
        <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface">{node.node}</span>
      </div>
      {node.detail && <p className="text-[11px] text-on-surface-variant mt-1">{node.detail}</p>}
      {node.children?.map((child: any, i: number) => (
        <LogicTreeNode key={i} node={child} />
      ))}
    </div>
  );
}

export default function EvaluationPanel({ result, onNoteGenerated }: EvaluationPanelProps) {
  const [note, setNote] = useState<string | null>(null);
  const [loadingNote, setLoadingNote] = useState(false);

  const riskClass =
    RISK_STYLES[result.risk_level] ?? "bg-surface-variant text-on-surface-variant";

  async function handleGenerateNote() {
    console.log("Starting EHR note generation for:", result.medication);
    setLoadingNote(true);
    setNote("System: Generating clinical documentation...");
    try {
      // Ensure we're sending a proper evaluation response structure
      const evaluationResponse = {
        status: result.status || "completed",
        patient_id: result.patient_id || "unknown",
        medication: result.medication,
        flagged: result.flagged,
        risk_level: result.risk_level,
        risk_summary: result.risk_summary,
        pathways: result.pathways || [],
        recommended_alternative: result.recommended_alternative,
        alternative_rationale: result.alternative_rationale,
        cpic_note: result.cpic_note || "",
        cpic_level: result.cpic_level,
        patient: result.patient,
        agent_steps: result.agent_steps || [],
        clinical_narrative: result.clinical_narrative,
        clinical_evidence: result.clinical_evidence,
        evidence_sources: result.evidence_sources || [],
        decision_confidence: result.decision_confidence,
        safety_notes: result.safety_notes || [],
        agent_verdict: result.agent_verdict,
        audit_trail: result.audit_trail || [],
        override_requirement: result.override_requirement,
        next_best_actions: result.next_best_actions || []
      };

      const res = await fetch("/api/clinical-note", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(evaluationResponse),
      });

      console.log("API Response status:", res.status);
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || data.detail || `Server responded with ${res.status}`);
      }

      if (!data.note) {
        throw new Error("Backend returned success but no note content was generated.");
      }

      console.log("Note received, length:", data.note.length);
      setNote(data.note);
      if (onNoteGenerated) onNoteGenerated(data.note);
    } catch (err) {
      console.error("EHR Generation Error:", err);
      const msg = err instanceof Error ? err.message : "Internal generation failure";
      setNote(`UNABLE TO GENERATE NOTE: ${msg}`);
    } finally {
      setLoadingNote(false);
      console.log("EHR generation process finished");
    }
  }

  return (
    <div className="glass-card rounded-xl overflow-hidden shadow-sm">
      <div className="bg-surface-container-low border-b border-outline-variant/30 px-6 py-4 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border border-outline-variant/20 ${riskClass}`}>
            {result.risk_level}
          </span>
          <h3 className="font-sans font-bold text-on-surface">
            Evaluation Summary: <span className="text-primary">{result.medication}</span>
          </h3>
        </div>
        <button
          onClick={handleGenerateNote}
          disabled={loadingNote}
          className="text-[10px] font-bold uppercase tracking-widest text-primary hover:bg-primary/5 px-3 py-1.5 rounded transition-all flex items-center gap-2"
        >
          <Icon name="description" className="h-4 w-4" />
          {loadingNote ? "Generating..." : "EHR Note"}
        </button>
      </div>

      <div className="p-6 space-y-6 bg-surface">
        {note && (
          <div className="relative rounded-lg border border-primary/20 bg-surface-container-low/30 p-5 animate-in slide-in-from-top-2 duration-300">
            <button 
              onClick={() => setNote(null)}
              className="absolute top-3 right-3 text-on-surface-variant hover:text-foreground"
            >
              <Icon name="close" className="h-4 w-4" />
            </button>
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-primary mb-3">Structured EHR Document</h4>
            <pre className="whitespace-pre-wrap text-[13px] font-serif text-on-surface leading-relaxed border-l-2 border-primary/20 pl-4">
              {note}
            </pre>
          </div>
        )}

        <div className="flex items-start gap-4">
           <div className={`mt-1 w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${result.flagged ? 'bg-error/10 text-error' : 'bg-primary/10 text-primary'}`}>
             <Icon name={result.flagged ? 'report_problem' : 'verified_user'} className="h-5 w-5" />
           </div>
           <div>
              <p className="text-base font-bold text-on-surface leading-snug">
                {result.risk_summary}
              </p>
              <p className="mt-1 text-xs text-on-surface-variant/80">
                CPIC Evidence Level: <span className="font-bold text-primary">{result.cpic_level || 'Informative'}</span>
              </p>
           </div>
        </div>

        <div className="rounded-lg border border-primary/15 bg-background p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant/60">
                Agent Verdict
              </p>
              <p className="mt-1 text-sm font-bold uppercase tracking-wider text-primary">
                {result.agent_verdict.replaceAll("_", " ")}
              </p>
            </div>
            <span
              className={`rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-widest ${
                result.override_requirement.required
                  ? "bg-error/10 text-error"
                  : "bg-primary/10 text-primary"
              }`}
            >
              {result.override_requirement.required ? "Override Required" : "No Override"}
            </span>
          </div>
          <p className="text-xs leading-relaxed text-on-surface-variant">
            {result.override_requirement.reason}
          </p>
          {result.override_requirement.required_fields.length > 0 && (
            <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2">
              {result.override_requirement.required_fields.map((field) => (
                <div
                  key={field}
                  className="rounded border border-outline-variant/30 bg-surface px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant"
                >
                  {field.replaceAll("_", " ")}
                </div>
              ))}
            </div>
          )}
        </div>

        {result.recommended_alternative && (
          <div className="bg-surface-container-low border border-primary/10 rounded-lg p-5">
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-primary mb-2">
               <Icon name="swap_horiz" className="h-4 w-4" />
               Recommended Alternative
            </div>
            <p className="text-xl font-bold text-on-surface">{result.recommended_alternative}</p>
            <p className="mt-2 text-xs text-on-surface-variant leading-relaxed italic border-t border-outline-variant/10 pt-2">
              {result.alternative_rationale}
            </p>
            <div className="mt-4">
               <PictogramStrip medication={result.recommended_alternative} />
            </div>
          </div>
        )}

        {result.next_best_actions.length > 0 && (
          <div className="rounded-lg border border-outline-variant/30 bg-surface p-5">
            <p className="mb-3 text-[10px] font-bold uppercase tracking-widest text-primary">
              Next Best Actions
            </p>
            <div className="space-y-3">
              {result.next_best_actions.map((action, index) => (
                <div key={action} className="flex gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-primary/10 text-[10px] font-bold text-primary">
                    {index + 1}
                  </span>
                  <p className="text-xs font-medium leading-relaxed text-on-surface-variant">
                    {action}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
           <div className="p-4 rounded-lg bg-background border border-outline-variant/20">
              <span className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant/60 block mb-1">Gene Target</span>
              <p className="text-xs font-mono font-bold text-on-surface">{result.patient?.cyp_profiles[0]?.gene} {result.patient?.cyp_profiles[0]?.diplotype}</p>
           </div>
           <div className="p-4 rounded-lg bg-background border border-outline-variant/20">
              <span className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant/60 block mb-1">Phenotype</span>
              <p className="text-xs font-bold text-on-surface">{result.patient?.cyp_profiles[0]?.phenotype}</p>
           </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
           <div className="p-4 rounded-lg bg-background border border-outline-variant/20">
              <span className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant/60 block mb-1">Decision Confidence</span>
              <p className="text-xs font-mono font-bold text-on-surface">{Math.round(result.decision_confidence * 100)}%</p>
           </div>
           <div className="p-4 rounded-lg bg-background border border-outline-variant/20">
              <span className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant/60 block mb-1">Evidence Sources</span>
              <p className="text-xs font-bold text-on-surface">
                {result.evidence_sources.length ? result.evidence_sources.join(", ") : "No source match"}
              </p>
           </div>
        </div>

        {result.clinical_narrative && (
          <div className="border-l-4 border-secondary/40 pl-5 py-2 bg-secondary-container/5 rounded-r-lg relative">
             <span className="absolute -top-2 -right-2 bg-surface-container-low text-[8px] font-bold text-on-surface-variant uppercase tracking-widest px-2 py-0.5 rounded border border-outline-variant/30">AI-Generated Advisory</span>
             <p className="text-sm font-serif italic text-on-surface-variant leading-relaxed mt-2">
               &quot;{result.clinical_narrative}&quot;
             </p>
          </div>
        )}

        {result.clinical_evidence && (
          <div className="rounded-lg border border-outline-variant/30 bg-surface-container-low/20 p-5 relative">
             <span className="absolute -top-2 -right-2 bg-surface-container-low text-[8px] font-bold text-on-surface-variant uppercase tracking-widest px-2 py-0.5 rounded border border-outline-variant/30">AI-Generated Advisory</span>
             <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-primary mb-3 mt-2">
                <span className="material-symbols-outlined text-sm">menu_book</span>
                Clinical Evidence Citation (RAG)
             </div>
             <div className="text-xs text-on-surface-variant leading-relaxed font-medium bg-white/50 p-4 rounded border border-outline-variant/10">
                {result.clinical_evidence}
             </div>
             <p className="mt-3 text-[9px] text-on-surface-variant/40 italic">
                Source: Semantic extraction from internal medical knowledge base. Verify with clinical judgment.
             </p>
          </div>
        )}


        {result.audit_trail.length > 0 && (
          <div className="rounded-lg border border-outline-variant/30 bg-background p-5">
            <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-primary">
              Safety Audit Trail
            </p>
            <div className="space-y-3">
              {result.audit_trail.map((event) => (
                <div key={event.stage} className="rounded border border-outline-variant/20 bg-surface p-3">
                  <div className="mb-1 flex items-center justify-between gap-3">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface">
                      {event.stage.replaceAll("_", " ")}
                    </p>
                    <span
                      className={`text-[9px] font-bold uppercase tracking-widest ${
                        event.requires_human_review ? "text-error" : "text-primary"
                      }`}
                    >
                      {event.decision.replaceAll("_", " ")}
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed text-on-surface-variant">
                    {event.rationale}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {result.logic_tree && result.logic_tree.node && (
          <div className="rounded-lg border border-outline-variant/30 bg-surface-container-low/10 p-5">
            <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-primary">
              Orchestration Logic Tree
            </p>
            <div className="bg-white/40 rounded border border-outline-variant/10 p-2">
               <LogicTreeNode node={result.logic_tree} />
            </div>
          </div>
        )}

        {result.safety_notes.length > 0 && (
          <div className="rounded-lg border border-outline-variant/30 bg-background p-4">
            <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant/60 mb-2">
              Safety Notes
            </p>
            <ul className="space-y-1">
              {result.safety_notes.map((note) => (
                <li key={note} className="text-xs text-on-surface-variant">
                  {note}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
