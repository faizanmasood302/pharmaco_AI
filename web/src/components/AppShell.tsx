"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import Icon from "./Icon";

export type Tab = "PRESCRIPTION" | "PIPELINE" | "PATHWAY" | "REPORTS" | "TRIAGE";

interface AppShellProps {
  children: (activeTab: Tab) => React.ReactNode;
}

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "PRESCRIPTION", label: "Prescription Console", icon: "medication" },
  { id: "PIPELINE", label: "AI Pipeline", icon: "insights" },
  { id: "PATHWAY", label: "Metabolic Pathways", icon: "account_tree" },
  { id: "REPORTS", label: "Clinical Reports", icon: "description" },
  { id: "TRIAGE", label: "Adherence Triage", icon: "assignment_ind" },
];

export default function AppShell({ children }: AppShellProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  
  // Get active tab from URL or default to PRESCRIPTION
  const initialTab = (searchParams.get("tab") as Tab) || "PRESCRIPTION";
  const [activeTab, setActiveTab] = useState<Tab>(initialTab);

  // Sync state with URL when tab changes
  const handleTabChange = (tabId: Tab) => {
    setActiveTab(tabId);
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", tabId);
    router.push(`${pathname}?${params.toString()}`);
  };

  // Sync state if URL changes externally (e.g. back button)
  useEffect(() => {
    const tab = searchParams.get("tab") as Tab;
    if (tab && tab !== activeTab) {
      setActiveTab(tab);
    }
  }, [searchParams, activeTab]);

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
            <div className="w-8 h-8 rounded-full bg-primary-container/30 border border-primary/20 overflow-hidden cursor-pointer hover:ring-2 ring-primary/30 transition-all">
               <Icon name="account_circle" className="h-full w-full p-1.5 text-primary" />
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
