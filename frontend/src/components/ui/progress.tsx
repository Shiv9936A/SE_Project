import { cn } from "@/lib/utils";

export function Progress({ value, className }: { value: number; className?: string }) {
  return <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={value} className={cn("h-2 w-full overflow-hidden rounded-full bg-slate-100", className)}>
    <div className="h-full rounded-full bg-blue-600 transition-all duration-500" style={{ width: `${value}%` }} />
  </div>;
}
