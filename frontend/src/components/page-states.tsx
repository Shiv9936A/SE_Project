import { AlertTriangle, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

export function PageLoading({ label = "Loading project data…" }: { label?: string }) {
  return <div role="status" className="flex min-h-56 items-center justify-center gap-3 text-sm text-slate-500"><LoaderCircle className="animate-spin" size={18} />{label}</div>;
}

export function PageError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-800"><div className="flex items-center gap-2 font-semibold"><AlertTriangle size={17} />Could not load this view</div><p className="mt-2">{message}</p><Button className="mt-4" variant="outline" onClick={onRetry}>Try again</Button></div>;
}
