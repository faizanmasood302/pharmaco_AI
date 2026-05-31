"use client";

import { useEffect, useState } from "react";
import type { EvaluationHistoryItem } from "@/lib/types";

interface EvaluationHistoryProps {
  patientId: string;
  refreshKey: number;
}

export default function EvaluationHistory({
  patientId,
  refreshKey,
}: EvaluationHistoryProps) {
  const [items, setItems] = useState<EvaluationHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!patientId) return;
    let cancelled = false;
    fetch(`/api/evaluations/${patientId}`)
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled) setItems(data.evaluations ?? []);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [patientId, refreshKey]);

  if (loading) {
    return (
      <p className="text-xs text-slate-500">Loading evaluation history…</p>
    );
  }

  if (items.length === 0) {
    return (
      <p className="text-xs text-slate-600">
        No persisted evaluations yet (requires Supabase) or run a new evaluation.
      </p>
    );
  }

  return (
    <div className="rounded-xl border border-outline/10 bg-surface/50 p-5 shadow-sm">
      <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">
        Patient Evaluation Archive
      </p>
      <ul className="max-h-40 space-y-2 overflow-y-auto">
        {items.map((item, i) => (
          <li
            key={item.id ?? i}
            className="flex items-center justify-between rounded border border-outline/5 bg-surface px-3 py-2.5 text-xs transition-colors hover:bg-background"
          >
            <span className="font-bold text-foreground">{item.medication}</span>
            <span
              className={`font-bold uppercase tracking-wider text-[10px] ${
                item.flagged ? "text-error" : "text-primary"
              }`}
            >
              {item.risk_level}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
