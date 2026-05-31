"use client";

import { useState } from "react";
import type { AdherencePlan, CheckIn } from "@/lib/types";
import Icon from "./Icon";

interface AdherencePanelProps {
  patientId: string;
  medication: string;
}

export default function AdherencePanel({
  patientId,
  medication,
}: AdherencePanelProps) {
  const [plan, setPlan] = useState<AdherencePlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [responses, setResponses] = useState<Record<string, string>>({});
  const [sideEffects, setSideEffects] = useState<Record<string, boolean>>({});
  const [feedback, setFeedback] = useState<string | null>(null);

  async function startPlan() {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch("/api/adherence/plans", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patient_id: patientId, medication }),
      });
      const data = await res.json();
      if (!res.ok) {
        setFeedback(data.error ?? "Failed to start plan");
        return;
      }
      setPlan({
        plan_id: data.plan_id,
        patient_id: data.patient_id,
        medication: data.medication,
        check_ins: data.check_ins ?? [],
        message: data.message,
      });
    } catch {
      setFeedback("Network error");
    } finally {
      setLoading(false);
    }
  }

  async function submitCheckIn(ci: CheckIn) {
    const res = await fetch(`/api/adherence/check-ins/${ci.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        response: responses[ci.id] ?? "",
        side_effect_reported: sideEffects[ci.id] ?? false,
      }),
    });
    const data = await res.json();
    if (res.ok) {
      setFeedback(
        JSON.stringify({
          reply: data.empathetic_reply,
          triage: data.triage
        })
      );
      setPlan((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          check_ins: prev.check_ins.map((c) =>
            c.id === ci.id ? { ...c, status: "completed" } : c
          ),
        };
      });
    }
  }

  const feedbackData = feedback && feedback.startsWith('{') ? JSON.parse(feedback) : null;

  if (!plan) {
    return (
      <div className="glass-card rounded-xl p-8 bg-surface-container-low/20">
        <h3 className="text-[10px] font-bold uppercase tracking-widest text-primary mb-3">Monitoring Protocol</h3>
        <p className="text-sm text-on-surface-variant leading-relaxed">
          Prescription authorized. Activate smart-adherence monitoring to track therapeutic baseline and metabolic risk factors.
        </p>
        <button
          type="button"
          onClick={startPlan}
          disabled={loading}
          className="mt-6 bg-primary text-on-primary text-[11px] font-bold uppercase tracking-widest py-3 px-6 rounded-lg hover:bg-primary/90 transition-all shadow-sm"
        >
          {loading ? "Initializing..." : "Enable Monitoring"}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between px-2">
        <h3 className="text-[10px] font-bold uppercase tracking-widest text-primary">Active Surveillance</h3>
        <span className="text-[10px] font-bold text-on-surface-variant/50">Plan ID: {plan.plan_id.slice(0,8)}</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {plan.check_ins.map((ci) => (
          <div
            key={ci.id}
            className="glass-card rounded-xl p-6 bg-surface flex flex-col h-full relative overflow-hidden"
          >
            <div className={`absolute top-0 left-0 w-1 h-full ${ci.status === 'completed' ? 'bg-primary' : 'bg-outline-variant/30'}`} />
            <div className="flex justify-between items-start mb-4">
               <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">Scheduled Log</span>
               {ci.status === 'completed' && <Icon name="check_circle" className="h-4 w-4 text-primary" />}
            </div>
            
            <p className="text-sm font-bold text-on-surface mb-4">{ci.prompt}</p>
            
            {ci.status === "completed" ? (
              <div className="mt-auto bg-background p-3 rounded text-[10px] font-medium text-primary uppercase tracking-widest flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                Data Synchronized
              </div>
            ) : (
              <div className="mt-auto space-y-4">
                <textarea
                  value={responses[ci.id] ?? ""}
                  onChange={(e) =>
                    setResponses((r) => ({ ...r, [ci.id]: e.target.value }))
                  }
                  rows={2}
                  className="input-clinical w-full bg-background px-3 py-2 text-xs rounded shadow-inner"
                  placeholder="Clinical observations..."
                />
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 text-xs font-bold text-on-surface-variant cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={sideEffects[ci.id] ?? false}
                      onChange={(e) =>
                        setSideEffects((s) => ({
                          ...s,
                          [ci.id]: e.target.checked,
                        }))
                      }
                      className="rounded border-outline/30 text-primary"
                    />
                    Side Effect Event
                  </label>
                  <button
                    type="button"
                    onClick={() => submitCheckIn(ci)}
                    className="bg-primary text-on-primary text-[10px] font-bold uppercase tracking-widest px-4 py-2 rounded hover:bg-primary/90 transition-all shadow-sm"
                  >
                    Log Entry
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
      
      {feedbackData && (
        <div className="glass-card rounded-xl p-8 bg-surface relative overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className={`absolute top-0 left-0 w-1.5 h-full ${
            feedbackData.triage.severity === 'HIGH' || feedbackData.triage.severity === 'CRITICAL' 
              ? 'bg-error' : 'bg-primary'
          }`} />
          <span className="absolute top-2 right-2 bg-surface-container-low text-[8px] font-bold text-on-surface-variant uppercase tracking-widest px-2 py-0.5 rounded border border-outline-variant/30">AI-Generated Triage</span>
          
          <div className="flex justify-between items-start mb-6 mt-2">
             <div className="flex items-center gap-2">
                <Icon
                  name={feedbackData.triage.severity === 'HIGH' || feedbackData.triage.severity === 'CRITICAL' ? 'warning' : 'info'}
                  className={`h-5 w-5 ${
                  feedbackData.triage.severity === 'HIGH' || feedbackData.triage.severity === 'CRITICAL' ? 'text-error' : 'text-primary'
                }`}
                />
                <span className={`text-[10px] font-bold uppercase tracking-widest ${
                  feedbackData.triage.severity === 'HIGH' || feedbackData.triage.severity === 'CRITICAL' ? 'text-error' : 'text-primary'
                }`}>
                  Triage Report: {feedbackData.triage.severity}
                </span>
             </div>
          </div>

          <div className="space-y-4">
            <div className="border-l-4 border-secondary/20 pl-4 py-1 mb-6">
               <p className="text-sm font-serif italic text-on-surface-variant">&ldquo;{feedbackData.reply}&rdquo;</p>
            </div>

            <div className="bg-background rounded-lg p-5 border border-outline-variant/30">
               <span className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant block mb-2">Clinical Directive</span>
               <p className="text-sm font-bold text-on-surface mb-2">Action: {feedbackData.triage.action}</p>
               <p className="text-xs text-on-surface-variant leading-relaxed">{feedbackData.triage.rationale}</p>
               <p className="mt-4 text-[9px] text-error font-bold uppercase tracking-widest italic border-t border-outline-variant/20 pt-2">
                 * Action required: Verify symptom severity with patient.
               </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
