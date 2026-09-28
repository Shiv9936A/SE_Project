import { Controller, type Control, type FieldErrors, type Path, type UseFormRegister } from "react-hook-form";
import type { ProjectForm } from "@/types/project";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type FieldProps = { label: string; hint?: string; error?: string; className?: string };

export function TextField({ name, label, hint, error, register, type = "text", placeholder, className }: FieldProps & {
  name: Path<ProjectForm>; register: UseFormRegister<ProjectForm>; type?: string; placeholder?: string;
}) {
  return <div className={cn("space-y-2", className)}>
    <Label htmlFor={name}>{label}</Label>
    {hint && <p className="-mt-1 text-xs leading-5 text-slate-500">{hint}</p>}
    <Input id={name} type={type} placeholder={placeholder} {...register(name, type === "number" ? { valueAsNumber: true } : undefined)} aria-invalid={!!error} />
    {error && <p className="text-xs font-medium text-rose-600">{error}</p>}
  </div>;
}

export function LongField({ name, label, hint, error, register, placeholder, rows = 4, className }: FieldProps & {
  name: Path<ProjectForm>; register: UseFormRegister<ProjectForm>; placeholder?: string; rows?: number;
}) {
  return <div className={cn("space-y-2", className)}>
    <Label htmlFor={name}>{label}</Label>
    {hint && <p className="-mt-1 text-xs leading-5 text-slate-500">{hint}</p>}
    <Textarea id={name} rows={rows} placeholder={placeholder} {...register(name)} aria-invalid={!!error} />
    {error && <p className="text-xs font-medium text-rose-600">{error}</p>}
  </div>;
}

export function SelectField({ name, label, options, error, register, placeholder = "Select an option" }: {
  name: Path<ProjectForm>; label: string; options: string[]; error?: string;
  register: UseFormRegister<ProjectForm>; placeholder?: string;
}) {
  return <div className="space-y-2">
    <Label htmlFor={name}>{label}</Label>
    <select id={name} className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-sm outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100" {...register(name)}>
      <option value="">{placeholder}</option>
      {options.map((option) => <option key={option} value={option}>{option}</option>)}
    </select>
    {error && <p className="text-xs font-medium text-rose-600">{error}</p>}
  </div>;
}

export function ChoiceField({ name, label, hint, options, control, errors }: {
  name: Path<ProjectForm>; label: string; hint?: string; options: string[];
  control: Control<ProjectForm>; errors: FieldErrors<ProjectForm>;
}) {
  const message = errors[name]?.message as string | undefined;
  return <Controller control={control} name={name} render={({ field }) => <fieldset className="space-y-3">
    <legend className="text-sm font-semibold text-slate-800">{label}</legend>
    {hint && <p className="-mt-2 text-xs text-slate-500">{hint}</p>}
    <div role="radiogroup" aria-label={label} className={cn("grid gap-2", options.length === 2 ? "grid-cols-2" : "grid-cols-1 sm:grid-cols-3")}>
      {options.map((option) => {
        const active = field.value === option;
        return <button key={option} type="button" role="radio" aria-checked={active} onClick={() => field.onChange(option)}
          className={cn("min-h-11 rounded-xl border px-3 py-2.5 text-sm font-medium transition", active ? "border-blue-500 bg-blue-50 text-blue-800 ring-2 ring-blue-100" : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50")}>
          {option}
        </button>;
      })}
    </div>
    {message && <p className="text-xs font-medium text-rose-600">{message}</p>}
  </fieldset>} />;
}
