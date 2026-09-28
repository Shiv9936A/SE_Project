import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes: number) {
  if (!bytes) return "0 B";
  const unit = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / 1024 ** unit).toFixed(unit ? 1 : 0)} ${["B", "KB", "MB", "GB"][unit]}`;
}
