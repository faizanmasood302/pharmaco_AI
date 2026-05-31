"use client";

import React from "react";
import { EvaluationResult } from "@/lib/types";
import Icon from "./Icon";

interface PathwayVisualizerProps {
  result: EvaluationResult;
}

export default function PathwayVisualizer({ result }: PathwayVisualizerProps) {
  // Find the relevant enzyme from the patient's profiles that matches the risk summary or pathways
  const relevantProfile = result.patient?.cyp_profiles?.find(p => 
    result.risk_summary.includes(p.gene) || 
    result.pathways.some(path => path.includes(p.gene))
  ) || result.patient?.cyp_profiles?.[0];

  const phenotype = relevantProfile?.phenotype ?? "Unknown";
  const enzyme = relevantProfile?.gene ?? "Enzyme";
  
  const pathwayStr = result.pathways[0] || "";
  const parts = pathwayStr.split("→").map(s => s.trim());
  
  // Extract drug and metabolite names from the pathway string
  const drugName = parts[0] || result.medication;
  const metabolitePart = parts[1] || "Metabolite";
  const rawMetaboliteName = metabolitePart.split("(")[0].trim();
  // Standardize capitalization (e.g., Morphine instead of morphine)
  const metaboliteName = rawMetaboliteName.charAt(0).toUpperCase() + rawMetaboliteName.slice(1);
  
  const isProdrug = pathwayStr.toLowerCase().includes("active metabolite") || pathwayStr.toLowerCase().includes("prodrug");

  const isUR = phenotype === "Ultra-Rapid Metabolizer";
  const isPM = phenotype === "Poor Metabolizer";
  const isIM = phenotype === "Intermediate Metabolizer";

  return (
    <div className="mt-4 p-8 bg-surface-container-lowest border border-outline-variant/30 rounded-xl">
      <div className="flex flex-col md:flex-row items-center justify-between gap-8">
        
        {/* Source Node (Parent Drug) */}
        <div className="w-44 bg-surface border border-outline-variant/50 rounded-lg p-5 shadow-sm flex flex-col items-center text-center">
          <Icon name="medication" className="mb-2 h-6 w-6 text-primary" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/80 mb-1">
            {isProdrug ? "Prodrug" : "Parent Drug"}
          </span>
          <span className="text-sm font-bold text-on-surface truncate w-full" title={drugName}>{drugName}</span>
          <span className="text-[10px] font-mono text-on-surface font-semibold mt-2 bg-background px-2 py-0.5 rounded border border-outline-variant/20">Administered</span>
        </div>

        {/* Enzyme Node (Center Catalyst) */}
        <div className="flex-1 flex flex-col items-center relative min-w-[150px]">
           {/* Arrow Left to Center */}
           <div className={`hidden md:block absolute right-1/2 top-1/2 w-1/2 h-[2px] -translate-y-1/2 ${isUR ? 'bg-error shadow-md' : 'bg-primary'}`} />
           
           <div className={`z-10 w-32 h-32 rounded-full flex flex-col items-center justify-center border-4 shadow-sm transition-all ${
             isUR ? 'border-error bg-error/10 scale-105 animate-pulse' : isPM ? 'border-outline dashed bg-background' : 'border-primary bg-primary/5'
           }`}>
             <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Enzyme</span>
             <span className={`text-lg font-bold ${isUR ? 'text-error' : 'text-primary'}`}>{enzyme}</span>
             <div className="mt-2 bg-white px-2 py-1 rounded text-[9px] font-bold font-mono shadow-sm text-on-surface border border-outline-variant/30">
                {phenotype.replace(" Metabolizer", "").toUpperCase()}
             </div>
           </div>

           {/* Arrow Center to Right (Directional Reaction) */}
           <div className={`hidden md:block absolute left-1/2 top-1/2 w-1/2 h-[2px] -translate-y-1/2 flex items-center justify-end ${
             isUR ? 'bg-error h-1' : isPM ? 'border-t-2 border-dashed border-outline/50' : 'bg-primary'
           }`}>
             {!isPM && (
               <div className={`w-0 h-0 border-y-4 border-l-[8px] border-y-transparent ${isUR ? 'border-l-error translate-x-1' : 'border-l-primary'}`} />
             )}
           </div>
        </div>

        {/* Metabolite Node (Output) */}
        <div className={`w-44 border rounded-lg p-5 shadow-sm flex flex-col items-center text-center transition-opacity ${
          isPM ? 'bg-surface-variant/30 border-outline-variant/30 opacity-60' : 'bg-surface border-outline-variant/50'
        }`}>
          <Icon name="science" className={`mb-2 h-6 w-6 ${isPM ? 'text-outline' : 'text-primary'}`} />
          <span className={`text-[10px] font-bold uppercase tracking-widest mb-1 ${isPM ? 'text-outline' : 'text-on-surface-variant/80'}`}>
            {isProdrug ? "Active Metabolite" : "Metabolite"}
          </span>
          <span className={`text-sm font-bold truncate w-full ${isPM ? 'text-outline' : 'text-on-surface'}`} title={metaboliteName}>{metaboliteName}</span>
          
          <div className="mt-3 w-full space-y-1 border-t border-outline-variant/10 pt-3">
             <div className="flex justify-between text-[9px] font-mono">
               <span className="text-on-surface-variant/70">Normal Formation:</span>
               <span className="text-on-surface font-bold">5-15%</span>
             </div>
             <div className="flex justify-between text-[9px] font-mono">
               <span className="text-on-surface-variant/70">Predicted Exposure:</span>
               <span className={`font-bold ${isUR ? 'text-error' : isPM ? 'text-outline' : 'text-primary'}`}>
                 {isUR ? "Elevated (>50%)" : isPM ? "Minimal" : isIM ? "Reduced" : "Standard"}
               </span>
             </div>
          </div>
        </div>
      </div>

      {/* Clinical Outcome / Consequence Box */}
      <div className={`mt-8 p-4 rounded-lg border flex items-center gap-4 animate-in fade-in slide-in-from-bottom-2 duration-500 ${
        isUR ? 'bg-error/5 border-error/20 text-error' : 
        isPM ? 'bg-background border-outline-variant/30 text-on-surface-variant' : 
        'bg-primary/5 border-primary/20 text-primary'
      }`}>
        <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
          isUR ? 'bg-error/10' : isPM ? 'bg-outline/10' : 'bg-primary/10'
        }`}>
          <Icon name={isUR ? 'warning' : isPM ? 'info' : 'check_circle'} className="h-5 w-5" />
        </div>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest opacity-70">Clinical Interpretation</p>
          <p className="text-sm font-bold leading-tight mt-0.5">
            {isUR ? "High risk of excessive opioid effect and respiratory toxicity." : 
             isPM ? "Treatment failure likely; parent drug remains inactive." : 
             "Expected therapeutic response with standard metabolic conversion."}
          </p>
        </div>
      </div>

      <div className="mt-8 pt-6 border-t border-outline-variant/20 flex flex-wrap justify-center gap-6">
         <div className="flex items-center gap-2 text-[10px] font-bold text-on-surface-variant uppercase tracking-tighter">
            <span className="w-3 h-0.5 bg-primary" /> Standard Conversion
         </div>
         <div className="flex items-center gap-2 text-[10px] font-bold text-error uppercase tracking-tighter">
            <span className="w-3 h-1 bg-error" /> Accelerated (High Risk)
         </div>
         <div className="flex items-center gap-2 text-[10px] font-bold text-outline uppercase tracking-tighter">
            <span className="w-3 border-t border-dashed border-outline" /> Blocked (Poor Efficacy)
         </div>
      </div>
    </div>
  );
}
