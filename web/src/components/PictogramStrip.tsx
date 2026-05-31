"use client";

interface PictogramStripProps {
  medication: string;
}

const TIPS: Record<string, {label: string }[]> = {
  Duloxetine: [
    {label: "Take with a food"},
    {label: "Avoid alcohol" },
    {label: "Same time daily" },
  ],
  Pregabalin: [
    {label: "Stay hydrated" },
    {label: "Caution driving until adjusted" },
    {label: "Do not skip doses" },
  ],
  default: [
    {label: "Follow clinician instructions" },
    {label: "Report side effects promptly" },
  ],
};

export default function PictogramStrip({ medication }: PictogramStripProps) {
  const tips = TIPS[medication] ?? TIPS.default;

  return (
    <div className="flex flex-wrap gap-2">
      {tips.map((tip) => (
        <div
          key={tip.label}
          className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-950/60 px-2.5 py-1.5"
          title={tip.label}
        >
          <span className="text-xs text-slate-400">{tip.label}</span>
        </div>
      ))}
    </div>
  );
}
