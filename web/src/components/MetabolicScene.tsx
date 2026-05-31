"use client";

import dynamic from "next/dynamic";
import { Suspense } from "react";

const MetabolicCanvas = dynamic(() => import("./MetabolicCanvas"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full min-h-[280px] items-center justify-center rounded-xl border border-cyan-500/20 bg-slate-950/80">
      <p className="text-sm text-cyan-400/70">Loading metabolic model…</p>
    </div>
  ),
});

interface MetabolicSceneProps {
  hasWarning: boolean;
  riskLevel?: 'optimal' | 'elevated' | 'critical';
}

export default function MetabolicScene({ hasWarning, riskLevel }: MetabolicSceneProps) {
  return (
    <Suspense fallback={null}>
      <MetabolicCanvas hasWarning={hasWarning} riskLevel={riskLevel} />
    </Suspense>
  );
}
