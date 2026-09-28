import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const styles = cva("inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:pointer-events-none disabled:opacity-50", {
  variants: {
    variant: {
      default: "bg-blue-600 text-white shadow-sm hover:bg-blue-700",
      outline: "border border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50",
      ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-950",
      secondary: "bg-blue-50 text-blue-700 hover:bg-blue-100",
    },
    size: { default: "h-11 px-5", sm: "h-9 px-3", lg: "h-12 px-6 text-base", icon: "size-10" },
  }, defaultVariants: { variant: "default", size: "default" },
});

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof styles> {}
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, ...props }, ref) => (
  <button ref={ref} className={cn(styles({ variant, size, className }))} {...props} />
));
Button.displayName = "Button";
