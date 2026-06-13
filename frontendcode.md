# Frontend Codebase

This file contains the core frontend components and API client.

## API Client (`web/src/lib/api.ts`)
```typescript
import { authClient } from "./auth-client";

const AGENT_SERVER =
  process.env.AGENT_SERVER_URL ?? "http://127.0.0.1:8000";

const FETCH_TIMEOUT = 15000; // 15 seconds

async function fetchWithTimeout(url: string, options: RequestInit & { timeout?: number } = {}) {
  const { timeout = FETCH_TIMEOUT, ...fetchOptions } = options;
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal
    });
    return response;
  } finally {
    clearTimeout(id);
  }
}

export async function getAuthToken(): Promise<string | null> {
  if (typeof window !== "undefined") {
    // Client-side: use authClient (document.cookie can't read HttpOnly cookies)
    const { data } = await authClient.getSession();
    return data?.session?.token ?? null;
  } else {
    // Server-side: Next.js cookies() can read HttpOnly cookies
    const { cookies } = await import("next/headers");
    const cookieStore = await cookies();
    return cookieStore.get("better-auth.session_token")?.value ?? null;
  }
}

async function handleApiError(response: Response) {
  try {
    const data = await response.json();
    return data.error?.message || data.detail || `Request failed with status ${response.status}`;
  } catch {
    return `HTTP ${response.status}: ${response.statusText}`;
  }
}

export async function proxyGet(path: string, explicitToken?: string) {
  const token = explicitToken ?? await getAuthToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetchWithTimeout(`${AGENT_SERVER}${path}`, { 
    headers,
    cache: "no-store" 
  }).catch(err => {
    console.error(`Fetch error for ${path}:`, err);
    throw new Error(`Agent Server unreachable at ${AGENT_SERVER}${path}: ${err.message}`);
  });
  
  if (!res.ok) {
    const errorMsg = await handleApiError(res);
    throw new Error(errorMsg);
  }

  const text = await res.text();
  return text ? JSON.parse(text) : {};
}

export async function proxyPost(path: string, body: unknown, explicitToken?: string) {
  const token = explicitToken ?? await getAuthToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetchWithTimeout(`${AGENT_SERVER}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  
  if (!res.ok) {
    const errorMsg = await handleApiError(res);
    throw new Error(errorMsg);
  }

  const text = await res.text();
  return text ? JSON.parse(text) : {};
}
```

## App Shell Component (`web/src/components/AppShell.tsx`)
```tsx
"use client";

import React, { useEffect, useState, useRef } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { authClient } from "@/lib/auth-client";
import Icon from "./Icon";

export type Tab =
  | "PRESCRIPTION"
  | "PIPELINE"
  | "PATHWAY"
  | "REPORTS"
  | "TRIAGE"
  | "RESEARCH";

interface AppShellProps {
  children: (activeTab: Tab) => React.ReactNode;
}

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "PRESCRIPTION", label: "Prescription Console", icon: "medication" },
  { id: "PIPELINE", label: "AI Pipeline", icon: "insights" },
  { id: "PATHWAY", label: "Metabolic Pathways", icon: "account_tree" },
  { id: "REPORTS", label: "Clinical Reports", icon: "description" },
  { id: "TRIAGE", label: "Adherence Triage", icon: "assignment_ind" },
  { id: "RESEARCH", label: "N-of-1 Research", icon: "science" },
];

export default function AppShell({ children }: AppShellProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const menuRef = useRef<HTMLDivElement>(null);
  
  // Get active tab from URL or default to PRESCRIPTION
  const requestedTab = searchParams.get("tab") as Tab | null;
  const initialTab: Tab =
    requestedTab && TABS.some((tab) => tab.id === requestedTab)
      ? requestedTab
      : "PRESCRIPTION";
  const [activeTab, setActiveTab] = useState<Tab>(initialTab);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  // Sync state with URL when tab changes
  const handleTabChange = (tabId: Tab) => {
    setActiveTab(tabId);
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", tabId);
    router.push(`${pathname}?${params.toString()}`);
  };

  // Handle clicks outside of profile menu to close it
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowProfileMenu(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await authClient.signOut();
      router.push("/login");
    } catch (error) {
      console.error("Logout failed:", error);
      setIsLoggingOut(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <nav className="hidden md:flex flex-col fixed left-0 top-0 h-full w-[240px] bg-surface-container-low border-r border-outline-variant/40 shadow-sm py-6 z-50">
        <div className="px-6 mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center text-on-primary shadow-sm">
              <Icon name="biotech" className="h-5 w-5" />
            </div>
            <div>
              <h1 className="font-sans text-lg font-extrabold text-primary leading-tight">GenomicLens MD</h1>
              <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/70">Precision Support</p>
            </div>
          </div>
          <button className="w-full mt-4 bg-primary text-on-primary text-[11px] font-bold uppercase tracking-widest py-2 px-4 rounded-lg hover:bg-primary/90 transition-colors shadow-sm flex items-center justify-center gap-2">
            <Icon name="search" className="h-[18px] w-[18px]" />
            Patient Search
          </button>
        </div>

        <div className="flex-1 overflow-y-auto mt-4 px-2">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`flex items-center w-[calc(100%-16px)] gap-3 rounded-xl px-4 py-3 mx-2 my-1 transition-all duration-200 cursor-pointer ${
                activeTab === tab.id
                  ? "bg-secondary-container text-on-secondary-container font-bold shadow-sm"
                  : "text-on-surface-variant hover:bg-primary-container/20 hover:text-primary active:scale-95"
              }`}
            >
              <Icon name={tab.icon} className="h-5 w-5" />
              <span className="text-xs font-bold">{tab.label}</span>
            </button>
          ))}
        </div>

        <div className="mt-auto pt-4 px-2 border-t border-outline-variant/30">
          <button className="flex items-center w-[calc(100%-16px)] gap-3 text-on-surface-variant px-4 py-3 mx-2 my-1 hover:bg-primary-container/20 hover:text-primary transition-all duration-200 rounded-xl cursor-pointer active:scale-95">
            <Icon name="help" className="h-5 w-5" />
            <span className="text-xs font-bold text-left">Support</span>
          </button>
          <button className="flex items-center w-[calc(100%-16px)] gap-3 text-on-surface-variant px-4 py-3 mx-2 my-1 hover:bg-primary-container/20 hover:text-primary transition-all duration-200 rounded-xl cursor-pointer active:scale-95">
            <Icon name="history" className="h-5 w-5" />
            <span className="text-xs font-bold text-left">Archive</span>
          </button>
        </div>
      </nav>

      {/* Main Content */}
      <div className="flex-1 flex flex-col md:ml-[240px] h-full overflow-hidden">
        <header className="bg-surface/80 backdrop-blur-md border-b border-outline-variant/30 shadow-sm flex justify-between items-center w-full px-4 md:px-10 h-16 z-40 shrink-0">
          <div className="md:hidden flex items-center gap-2">
            <span className="font-sans text-lg font-bold text-primary">GenomicLens</span>
          </div>
          <div className="hidden md:block flex-1">
            <h2 className="font-sans text-lg font-bold text-primary">
              {TABS.find(t => t.id === activeTab)?.label}
            </h2>
          </div>
          <div className="flex items-center gap-4">
            <button className="text-on-surface-variant hover:bg-surface-variant/50 hover:text-primary transition-all duration-200 p-2 rounded-full active:scale-[0.98]">
              <Icon name="notifications" className="h-5 w-5" />
            </button>
            <button className="text-on-surface-variant hover:bg-surface-variant/50 hover:text-primary transition-all duration-200 p-2 rounded-full active:scale-[0.98]">
              <Icon name="settings" className="h-5 w-5" />
            </button>
            <div className="h-8 w-px bg-outline-variant/30 mx-1"></div>
            <div className="relative" ref={menuRef}>
              <div 
                onClick={() => setShowProfileMenu(!showProfileMenu)}
                className="w-8 h-8 rounded-full bg-primary-container/30 border border-primary/20 overflow-hidden cursor-pointer hover:ring-2 ring-primary/30 transition-all flex items-center justify-center"
              >
                <Icon name="account_circle" className="h-full w-full p-1.5 text-primary" />
              </div>
              
              {showProfileMenu && (
                <div className="absolute right-0 mt-2 w-56 bg-surface border border-outline-variant/30 rounded-2xl shadow-2xl py-2 z-50 animate-in fade-in zoom-in-95 duration-150">
                  <div className="px-4 py-3 border-b border-outline-variant/20 mb-2">
                    <p className="text-[10px] font-bold text-on-surface-variant/60 uppercase tracking-widest">Active Practitioner</p>
                    <p className="text-xs font-bold text-primary truncate mt-0.5">Clinical Staff</p>
                  </div>
                  
                  <button className="w-[calc(100%-16px)] mx-2 flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-primary/10 text-on-surface-variant hover:text-primary transition-all group">
                    <Icon name="person" className="h-4 w-4" />
                    <span className="text-xs font-bold">Clinical Profile</span>
                  </button>
                  
                  <button className="w-[calc(100%-16px)] mx-2 flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-primary/10 text-on-surface-variant hover:text-primary transition-all group">
                    <Icon name="security" className="h-4 w-4" />
                    <span className="text-xs font-bold">Access Logs</span>
                  </button>
                  
                  <div className="h-px bg-outline-variant/20 my-2 mx-4"></div>
                  
                  <button 
                    onClick={handleLogout}
                    disabled={isLoggingOut}
                    className="w-[calc(100%-16px)] mx-2 flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-error/10 text-error transition-all group active:scale-95"
                  >
                    <Icon name={isLoggingOut ? "progress_activity" : "logout"} className={`h-4 w-4 ${isLoggingOut ? 'animate-spin' : ''}`} />
                    <span className="text-xs font-bold">End Session</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 md:p-10 bg-background">
          <div className="max-w-7xl mx-auto">
            {children(activeTab)}
          </div>
        </main>
      </div>
    </div>
  );
}
```

## Evaluation Panel Component (`web/src/components/EvaluationPanel.tsx`)
```tsx
"use client";

import { useState } from "react";
import type { EvaluationResult, LogicTreeNodeData } from "@/lib/types";
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
  onReviewDecision?: (
    decision: "approved" | "rejected",
    rationale: string
  ) => Promise<boolean> | boolean;
}

function LogicTreeNode({ node }: { node: LogicTreeNodeData }) {
  return (
    <div className="ml-4 border-l border-outline-variant/30 pl-4 py-2">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${node.flag ? 'bg-error' : 'bg-primary'}`} />
        <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface">{node.node}</span>
      </div>
      {node.detail && <p className="text-[11px] text-on-surface-variant mt-1">{node.detail}</p>}
      {node.children?.map((child, i) => (
        <LogicTreeNode key={i} node={child} />
      ))}
    </div>
  );
}

export default function EvaluationPanel({ result, onNoteGenerated, onReviewDecision }: EvaluationPanelProps) {
  const [note, setNote] = useState<string | null>(null);
  const [loadingNote, setLoadingNote] = useState(false);
  const [reviewNote, setReviewNote] = useState("");
  const [decisionLoading, setDecisionLoading] = useState(false);

  const riskClass =
    RISK_STYLES[result.risk_level] ?? "bg-surface-variant text-on-surface-variant";

  async function handleGenerateNote() {
    setLoadingNote(true);
    setNote("System: Generating clinical documentation...");
    try {
      const res = await fetch("/api/clinical-note", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(result),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Generation failure");

      setNote(data.note);
      if (onNoteGenerated) onNoteGenerated(data.note);
    } catch (err) {
      console.error("EHR Generation Error:", err);
      setNote("UNABLE TO GENERATE NOTE");
    } finally {
      setLoadingNote(false);
    }
  }

  async function handleReviewDecision(decision: "approved" | "rejected") {
    if (!onReviewDecision) return;
    setDecisionLoading(true);
    try {
      const saved = await onReviewDecision(decision, reviewNote.trim());
      if (saved) {
        setReviewNote("");
      }
    } catch (err) {
      console.error("Decision click error:", err);
    } finally {
      setDecisionLoading(false);
    }
  }

  return (
    <div className="glass-card rounded-xl overflow-hidden shadow-sm">
      {/* (Component JSX implementation ...) */}
    </div>
  );
}
```

## Therapy Simulation Panel (`web/src/components/TherapySimulationPanel.tsx`)
```tsx
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

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
      {/* (Component JSX implementation ...) */}
    </div>
  );
}
```
*(Component JSX content truncated for brevity in this documentation file)*
