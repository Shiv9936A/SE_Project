import { ArrowLeft, ArrowRight, Check, CircleHelp, FileText, ShieldCheck, Sparkles, MessageCircleQuestion } from "lucide-react";
import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { Badge } from "@/components/ui/badge";

export function TopBar({ backTo, backLabel = "Back to home" }: { backTo?: string; backLabel?: string }) {
  return <header className="flex items-center justify-between border-b border-slate-200/80 bg-white/85 px-5 py-4 backdrop-blur md:px-10">
    <Link to="/" className="flex items-center gap-3 text-slate-900 no-underline">
      <span className="grid size-10 place-items-center rounded-xl bg-blue-600 text-white"><Sparkles size={19} /></span>
      <span><span className="block text-sm font-bold tracking-tight">Requirements Studio</span><span className="block text-[11px] text-slate-500">Project discovery</span></span>
    </Link>
    {backTo && <Link to={backTo} className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 no-underline hover:text-slate-900"><ArrowLeft size={15} />{backLabel}</Link>}
  </header>;
}

export function ProjectNavigation({ projectId }: { projectId: string }) {
  const items = [
    ["Overview", `/projects/${projectId}`],
    ["Questionnaire", `/projects/${projectId}/questionnaire`],
    ["AI Analysis", `/projects/${projectId}/analysis`],
    ["SDLC recommendation", `/projects/${projectId}/recommendation`],
    ["AI assistant", `/projects/${projectId}/chat`],
    ["Documents", `/projects/${projectId}/documents`],
  ];
  return <nav aria-label="Project navigation" className="mb-7 flex flex-wrap gap-2 rounded-2xl border border-slate-200 bg-white p-2">
    {items.map(([label, to]) => <NavLink key={to} end={label === "Overview"} to={to} className={({ isActive }) => `rounded-xl px-3 py-2 text-xs font-semibold no-underline transition sm:px-4 sm:text-sm ${isActive ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</NavLink>)}
  </nav>;
}

export function PageFrame({ children, projectId }: { children: ReactNode; projectId?: string }) {
  return <div className="min-h-screen bg-[#f5f7fb]"><TopBar /><main className="mx-auto w-full max-w-6xl px-4 py-8 md:px-8 md:py-12">{projectId && <ProjectNavigation projectId={projectId} />}{children}</main></div>;
}

export const wizardSteps = [
  { title: "Project profile", short: "Profile", icon: FileText },
  { title: "Adaptive interview", short: "Interview", icon: MessageCircleQuestion },
  { title: "Requirements & change", short: "Requirements", icon: ArrowRight },
  { title: "Risk & assurance", short: "Assurance", icon: ShieldCheck },
  { title: "Delivery context", short: "Delivery", icon: CircleHelp },
  { title: "Reference files", short: "Files", icon: FileText },
  { title: "Review & submit", short: "Review", icon: Check },
];

export function StepProgress({ active }: { active: number }) {
  const progress = Math.round((active / (wizardSteps.length - 1)) * 100);
  return <section className="mb-7 rounded-2xl border border-slate-200 bg-white px-5 py-5 shadow-sm md:px-7">
    <div className="mb-3 flex items-center justify-between"><span className="text-sm font-semibold text-slate-800">Step {active + 1} of {wizardSteps.length}</span><Badge>{progress}% complete</Badge></div>
    <div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600 transition-all duration-500" style={{ width: `${progress}%` }} /></div>
    <div className="mt-4 hidden grid-cols-7 gap-2 md:grid">{wizardSteps.map((step, index) => <div key={step.short} className={`text-xs ${index <= active ? "font-semibold text-blue-700" : "text-slate-400"}`}>{step.short}</div>)}</div>
  </section>;
}

export function NavButtons({ onBack, onNext, backDisabled, nextDisabled, nextLabel = "Continue" }: {
  onBack: () => void; onNext: () => void; backDisabled?: boolean; nextDisabled?: boolean; nextLabel?: string;
}) {
  return <div className="mt-8 flex items-center justify-between border-t border-slate-100 pt-5">
    <button type="button" onClick={onBack} disabled={backDisabled} className="inline-flex h-11 items-center gap-2 rounded-xl px-4 text-sm font-semibold text-slate-600 hover:bg-slate-100 disabled:invisible"><ArrowLeft size={16} />Previous</button>
    <button type="button" onClick={onNext} disabled={nextDisabled} className="inline-flex h-11 items-center gap-2 rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60">{nextLabel}<ArrowRight size={16} /></button>
  </div>;
}
