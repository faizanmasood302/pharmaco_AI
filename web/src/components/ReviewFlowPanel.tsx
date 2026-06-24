"use client";

import { useState } from "react";
import type { EvaluationResult, LogicTreeNodeData, AuditEvent, AgentStep } from "@/lib/types";
import Icon from "./Icon";

const RISK_COLORS: Record<string, string> = {
  none: "text-primary",
  low: "text-primary",
  moderate: "text-amber-600",
  high: "text-orange-600",
  critical: "text-error",
};

const SEVERITY_ICONS: Record<string, string> = {
  info: "info",
  warning: "warning",
  critical: "report_problem",
};

function AgentStepCard({ step, index, total }: { step: AgentStep; index: number; total: number }) {
  const [expanded, setExpanded] = useState(false);

  const displayStatus =
    step.agent === "HumanGate" ? (step.status === "pending" ? "pending" : step.status) : step.status;
  const isComplete = displayStatus === "complete" || displayStatus === "approved";
  const isFailed = displayStatus === "blocked" || displayStatus === "rejected";

  return (
    <div className="flex gap-5 relative group">
      <div className="flex flex-col items-center shrink-0">
        <div
          className={`w-9 h-9 rounded-lg flex items-center justify-center z-10 transition-all ${
            isComplete
              ? "bg-primary text-on-primary shadow-sm"
              : isFailed
                ? "bg-error text-on-error"
                : "bg-background text-outline border border-outline/20"
          }`}
        >
          <Icon
            name={
              step.agent === "Retrieval" || step.agent === "Research"
                ? "search"
                : step.agent === "Reasoning" || step.agent === "Analyst"
                  ? "psychology"
                  : step.agent === "Critic"
                    ? "verified_user"
                    : step.agent === "Knowledge"
                      ? "menu_book"
                      : step.agent === "Policy"
                        ? "gavel"
                        : step.agent === "Reporter"
                          ? "description"
                          : step.agent === "HumanGate"
                            ? "fact_check"
                            : step.agent === "Challenge"
                              ? "report_problem"
                              : step.agent === "Orchestrator"
                                ? "hub"
                                : "analytics"
            }
            className="h-4 w-4"
          />
        </div>
        {index < total - 1 && <div className="w-0.5 flex-1 bg-outline-variant/20 my-1.5" />}
      </div>
      <div className={`pb-6 pt-0.5 flex-1 min-w-0 ${index < total - 1 ? "border-b border-outline-variant/10" : ""}`}>
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 w-full text-left cursor-pointer group/btn"
        >
          <span
            className={`text-[11px] font-bold uppercase tracking-wider ${
              isComplete
                ? "text-primary"
                : isFailed
                  ? "text-error"
                  : "text-on-surface-variant"
            }`}
          >
            {step.agent === "HumanGate" ? "Human Gate" : step.agent}
          </span>
          <span
            className={`text-[8px] font-bold px-1.5 py-0.5 rounded uppercase ${
              isComplete
                ? "bg-primary/10 text-primary"
                : isFailed
                  ? "bg-error/10 text-error"
                  : "bg-background text-on-surface-variant border border-outline/20"
            }`}
          >
            {displayStatus}
          </span>
          <span className="ml-auto flex items-center gap-2 text-[9px] font-mono text-on-surface-variant/40">
            {step.duration_ms != null && <span>{step.duration_ms}ms</span>}
            <Icon
              name={expanded ? "expand_less" : "expand_more"}
              className="h-4 w-4 text-on-surface-variant/30 group-hover/btn:text-on-surface-variant/60"
            />
          </span>
        </button>
        <p className="text-xs text-on-surface-variant leading-relaxed mt-1 bg-background/30 p-3 rounded border border-outline-variant/10">
          {step.summary}
        </p>
        {expanded && (
          <div className="mt-3 space-y-2 animate-in slide-in-from-top-2 duration-200">
            {typeof step.confidence === "number" && (
              <div className="flex items-center gap-2 text-[10px] font-mono text-on-surface-variant/50 bg-background/50 px-3 py-1.5 rounded border border-outline-variant/10">
                <Icon name="trending_up" className="h-3 w-3" />
                Confidence: {Math.round(step.confidence * 100)}%
              </div>
            )}
            {step.evidence_refs && step.evidence_refs.length > 0 && (
              <div className="bg-background/50 px-3 py-1.5 rounded border border-outline-variant/10">
                <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant/40 mb-1">
                  Citations
                </p>
                <div className="flex flex-wrap gap-1">
                  {step.evidence_refs.map((ref) => (
                    <span
                      key={`${step.agent}-${ref}`}
                      className="text-[9px] font-mono bg-primary/5 text-primary px-1.5 py-0.5 rounded border border-primary/10"
                    >
                      {ref}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function LogicTreeView({ node, depth = 0 }: { node: LogicTreeNodeData; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 2);

  if (!node || !node.node) return null;

  const hasChildren = node.children && node.children.length > 0;

  return (
    <div className="select-none">
      <div
        className={`flex items-start gap-2 py-1.5 px-2 rounded hover:bg-background/60 transition-colors cursor-pointer ${
          node.flag ? "bg-error/5 border-l-2 border-error" : "border-l-2 border-transparent"
        }`}
        style={{ marginLeft: `${depth * 20}px` }}
        onClick={() => hasChildren && setExpanded(!expanded)}
      >
        {hasChildren ? (
          <Icon
            name={expanded ? "expand_more" : "chevron_right"}
            className="h-4 w-4 mt-0.5 text-on-surface-variant/40 shrink-0"
          />
        ) : (
          <div className="w-4 shrink-0" />
        )}
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${node.flag ? "bg-error" : "bg-primary"}`} />
            <span className="text-[11px] font-bold text-on-surface">{node.node}</span>
          </div>
          {node.detail && (
            <p className="text-[10px] text-on-surface-variant mt-0.5 ml-3.5 leading-relaxed">{node.detail}</p>
          )}
        </div>
      </div>
      {hasChildren && expanded && (
        <div className="ml-2 border-l border-outline-variant/20">
          {node.children!.map((child, i) => (
            <LogicTreeView key={i} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

function AuditTrailSection({ events }: { events: AuditEvent[] }) {
  const [filter, setFilter] = useState<"all" | "review" | "auto">("all");

  const filtered = events.filter((e) => {
    if (filter === "review") return e.requires_human_review;
    if (filter === "auto") return !e.requires_human_review;
    return true;
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-1">
          {(["all", "review", "auto"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`text-[9px] font-bold uppercase tracking-wider px-2.5 py-1 rounded transition-colors cursor-pointer ${
                filter === f ? "bg-primary text-on-primary" : "bg-background text-on-surface-variant hover:bg-primary/10"
              }`}
            >
              {f === "all" ? "All" : f === "review" ? "Human Review" : "Auto"}
            </button>
          ))}
        </div>
        <span className="text-[9px] font-mono text-on-surface-variant/40">{filtered.length} events</span>
      </div>
      <div className="space-y-2">
        {filtered.map((event) => (
          <div
            key={event.stage + event.decision}
            className={`rounded border p-3 transition-colors ${
              event.requires_human_review
                ? "border-amber-200 bg-amber-50/30 hover:bg-amber-50/50"
                : "border-outline-variant/20 bg-surface hover:bg-surface-container-low/50"
            }`}
          >
            <div className="flex items-center justify-between gap-3 mb-1">
              <div className="flex items-center gap-2 min-w-0">
                <Icon
                  name={event.requires_human_review ? SEVERITY_ICONS.warning : SEVERITY_ICONS.info}
                  className={`h-3.5 w-3.5 shrink-0 ${event.requires_human_review ? "text-amber-500" : "text-primary"}`}
                />
                <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface truncate">
                  {event.stage.replaceAll("_", " ")}
                </span>
              </div>
              <span
                className={`text-[8px] font-bold uppercase tracking-wider shrink-0 px-1.5 py-0.5 rounded ${
                  event.requires_human_review
                    ? "bg-amber-100 text-amber-700"
                    : "bg-primary/10 text-primary"
                }`}
              >
                {event.decision.replaceAll("_", " ")}
              </span>
            </div>
            <p className="text-[11px] text-on-surface-variant leading-relaxed">{event.rationale}</p>
          </div>
        ))}
        {filtered.length === 0 && (
          <p className="text-xs text-on-surface-variant/50 italic text-center py-6">
            No {filter === "review" ? "human review" : filter === "auto" ? "auto" : ""} events recorded.
          </p>
        )}
      </div>
    </div>
  );
}

interface ReviewFlowPanelProps {
  result: EvaluationResult | null;
}

export default function ReviewFlowPanel({ result }: ReviewFlowPanelProps) {
  const [activeSection, setActiveSection] = useState<"agents" | "logic" | "evidence" | "audit">("agents");

  if (!result) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="glass-card rounded-xl p-20 text-center text-on-surface-variant bg-surface/40">
          <Icon name="account_tree" className="mx-auto mb-4 h-12 w-12 opacity-10" />
          <p className="font-bold text-on-surface">No Review Flow Available</p>
          <p className="mt-1 text-xs max-w-sm mx-auto">
            Run a prescription evaluation to inspect the full multi-agent debate trace, logic tree, evidence citations, and audit trail.
          </p>
        </div>
      </div>
    );
  }

  const sections = [
    { id: "agents" as const, label: "Agent Timeline", icon: "psychology", count: result.agent_steps.length },
    { id: "logic" as const, label: "Logic Tree", icon: "account_tree", count: 1 },
    { id: "evidence" as const, label: "Evidence Sources", icon: "menu_book", count: result.evidence_sources.length },
    { id: "audit" as const, label: "Audit Trail", icon: "fact_check", count: result.audit_trail.length },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-on-surface">Multi-Agent Review Flow</h2>
          <p className="text-sm text-on-surface-variant mt-1">
            Full reasoning trace for <span className="font-bold text-primary">{result.medication}</span> +{" "}
            <span className="font-bold text-primary">{result.patient_id}</span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-[10px] font-bold uppercase tracking-wider ${RISK_COLORS[result.risk_level] || "text-on-surface-variant"}`}>
            {result.risk_level}
          </span>
          <span className={`px-3 py-1 rounded-full text-[9px] font-bold uppercase tracking-wider border ${
            result.flagged ? "bg-error/10 text-error border-error/20" : "bg-primary/10 text-primary border-primary/20"
          }`}>
            {result.flagged ? "Flagged" : "Cleared"}
          </span>
        </div>
      </div>

      <div className="flex gap-1 bg-surface-container-low/50 p-1 rounded-lg border border-outline-variant/20">
        {sections.map((s) => (
          <button
            key={s.id}
            onClick={() => setActiveSection(s.id)}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all cursor-pointer ${
              activeSection === s.id
                ? "bg-surface text-primary shadow-sm"
                : "text-on-surface-variant hover:text-primary hover:bg-surface/50"
            }`}
          >
            <Icon name={s.icon} className="h-4 w-4" />
            {s.label}
            <span className="text-[8px] font-mono opacity-50">({s.count})</span>
          </button>
        ))}
      </div>

      <div className="glass-card rounded-xl p-6 md:p-8 animate-in fade-in duration-300">
        {activeSection === "agents" && (
          <div>
            <div className="flex items-center justify-between mb-8 border-b border-outline-variant/20 pb-4">
              <div>
                <h3 className="text-sm font-bold text-on-surface uppercase tracking-wider">Agent Execution Timeline</h3>
                <p className="text-[10px] text-on-surface-variant mt-0.5">
                  {result.agent_steps.length} agents ·{" "}
                  Total confidence: {result.agent_steps.length > 0
                    ? Math.round(
                        result.agent_steps.reduce((s, a) => s + (a.confidence ?? 0), 0) /
                          result.agent_steps.length * 100
                      )
                    : 0}%
                </p>
              </div>
              <div className={`text-[10px] font-bold uppercase tracking-wider ${RISK_COLORS[result.risk_level] || ""}`}>
                {result.agent_verdict.replaceAll("_", " ")}
              </div>
            </div>
            {result.agent_steps.length > 0 ? (
              result.agent_steps.map((step, idx) => (
                <AgentStepCard key={idx} step={step} index={idx} total={result.agent_steps.length} />
              ))
            ) : (
              <p className="text-xs text-on-surface-variant/50 italic text-center py-8">No agent steps recorded.</p>
            )}
          </div>
        )}

        {activeSection === "logic" && (
          <div>
            <div className="mb-6 border-b border-outline-variant/20 pb-4">
              <h3 className="text-sm font-bold text-on-surface uppercase tracking-wider">Orchestration Logic Tree</h3>
              <p className="text-[10px] text-on-surface-variant mt-0.5">
                Decision tree from the multi-agent orchestration pipeline. Red indicates flagged nodes.
              </p>
            </div>
            {result.logic_tree && result.logic_tree.node ? (
              <div className="bg-background/30 rounded-lg border border-outline-variant/10 p-4">
                <LogicTreeView node={result.logic_tree} />
              </div>
            ) : (
              <p className="text-xs text-on-surface-variant/50 italic text-center py-8">No logic tree data available.</p>
            )}
          </div>
        )}

        {activeSection === "evidence" && (
          <div>
            <div className="mb-6 border-b border-outline-variant/20 pb-4">
              <h3 className="text-sm font-bold text-on-surface uppercase tracking-wider">Evidence & Citations</h3>
              <p className="text-[10px] text-on-surface-variant mt-0.5">
                CPIC guidelines, PharmGKB annotations, and FDA labels referenced during evaluation.
              </p>
            </div>

            <div className="space-y-4">
              <div className="bg-background/30 rounded-lg border border-outline-variant/10 p-5">
                <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant/50 mb-2">
                  CPIC Guideline
                </p>
                <p className="text-xs text-on-surface-variant leading-relaxed">
                  {result.cpic_note || "No CPIC note recorded."}
                </p>
                {result.cpic_level && (
                  <span className="mt-2 inline-block text-[9px] font-bold uppercase tracking-wider bg-primary/10 text-primary px-2 py-0.5 rounded">
                    Level: {result.cpic_level}
                  </span>
                )}
              </div>

              {result.evidence_sources.length > 0 && (
                <div className="bg-background/30 rounded-lg border border-outline-variant/10 p-5">
                  <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant/50 mb-3">
                    Source References ({result.evidence_sources.length})
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {result.evidence_sources.map((source, idx) => (
                      <span
                        key={`ev-${idx}`}
                        className="text-[10px] font-mono bg-primary/5 text-primary border border-primary/10 px-2.5 py-1 rounded"
                      >
                        {source}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {result.clinical_evidence && (
                <div className="bg-background/30 rounded-lg border border-outline-variant/10 p-5">
                  <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant/50 mb-2">
                    Retrieved Evidence
                  </p>
                  <p className="text-xs text-on-surface-variant leading-relaxed bg-white/40 p-3 rounded border border-outline-variant/10">
                    {result.clinical_evidence}
                  </p>
                </div>
              )}

              {result.clinical_narrative && (
                <div className="border-l-4 border-secondary/40 pl-4 py-3 bg-secondary/5 rounded-r-lg">
                  <p className="text-[9px] font-bold uppercase tracking-widest text-secondary mb-1">
                    Clinical Narrative
                  </p>
                  <p className="text-xs font-serif italic text-on-surface-variant leading-relaxed">
                    &quot;{result.clinical_narrative}&quot;
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {activeSection === "audit" && (
          <div>
            <div className="mb-6 border-b border-outline-variant/20 pb-4">
              <h3 className="text-sm font-bold text-on-surface uppercase tracking-wider">Safety Audit Trail</h3>
              <p className="text-[10px] text-on-surface-variant mt-0.5">
                Chronological record of all decisions, reviews, and overrides.
              </p>
            </div>
            {result.audit_trail.length > 0 ? (
              <AuditTrailSection events={result.audit_trail} />
            ) : (
              <p className="text-xs text-on-surface-variant/50 italic text-center py-8">No audit events recorded.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
