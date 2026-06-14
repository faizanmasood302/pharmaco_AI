"use client";

import { createContext, useCallback, useContext, useState } from "react";
import Icon from "./Icon";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, type: ToastType = "info") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const removeToast = (id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const iconMap: Record<ToastType, string> = {
    success: "check_circle",
    error: "error",
    info: "info",
  };

  const colorMap: Record<ToastType, string> = {
    success: "bg-primary text-on-primary shadow-lg shadow-primary/20",
    error: "bg-error text-white shadow-lg shadow-error/20",
    info: "bg-surface text-on-surface border border-outline-variant/30 shadow-lg",
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-3 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto toast-enter rounded-xl px-5 py-4 flex items-center gap-3 min-w-[300px] max-w-[420px] ${colorMap[t.type]}`}
          >
            <Icon name={iconMap[t.type]} className="h-5 w-5 shrink-0" />
            <p className="text-xs font-bold flex-1">{t.message}</p>
            <button
              onClick={() => removeToast(t.id)}
              className="opacity-60 hover:opacity-100 transition-opacity"
            >
              <Icon name="close" className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
