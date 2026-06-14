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
          <div className="mt-3 px-2 py-1 bg-secondary/10 rounded-lg border border-secondary/20">
            <p className="text-[9px] font-bold text-secondary uppercase tracking-[0.15em] text-center">
              Research Simulation
            </p>
          </div>
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
          <div className="px-4 py-3 mx-2">
            <p className="text-[9px] font-bold text-on-surface-variant/40 uppercase tracking-[0.15em] leading-relaxed">
              Pharmacogenomic Harness v0.2.0<br />
              <span className="text-[8px]">Not for clinical use</span>
            </p>
          </div>
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
