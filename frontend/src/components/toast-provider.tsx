import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { X } from "lucide-react";

type ToastItem = { id: number; message: string; tone: "success" | "error" | "info" };
type ToastContextValue = { toast: (message: string, tone?: ToastItem["tone"]) => void };

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const toast = useCallback((message: string, tone: ToastItem["tone"] = "info") => {
    const id = Date.now() + Math.random();
    setItems((current) => [...current, { id, message, tone }]);
    window.setTimeout(() => setItems((current) => current.filter((item) => item.id !== id)), 5000);
  }, []);

  return <ToastContext.Provider value={{ toast }}>
    {children}
    <div className="fixed right-4 top-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
      {items.map((item) => <div key={item.id} role={item.tone === "error" ? "alert" : "status"} className={`flex items-start justify-between gap-3 rounded-xl border bg-white p-4 text-sm shadow-lg ${item.tone === "error" ? "border-rose-200 text-rose-800" : item.tone === "success" ? "border-emerald-200 text-emerald-800" : "border-slate-200 text-slate-700"}`}>
        <span>{item.message}</span><button aria-label="Dismiss notification" onClick={() => setItems((current) => current.filter((toastItem) => toastItem.id !== item.id))}><X size={16} /></button>
      </div>)}
    </div>
  </ToastContext.Provider>;
}

export function useToast() {
  const value = useContext(ToastContext);
  if (!value) throw new Error("useToast must be used inside ToastProvider.");
  return value.toast;
}
