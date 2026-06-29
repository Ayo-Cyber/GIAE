import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBp(bp: number): string {
  if (bp >= 1_000_000) return `${(bp / 1_000_000).toFixed(2)} Mbp`;
  if (bp >= 1_000) return `${(bp / 1_000).toFixed(1)} kbp`;
  return `${bp} bp`;
}

export function confidenceColor(level: string | null) {
  switch (level) {
    case "HIGH": return "text-emerald-400";
    case "MODERATE": return "text-amber-400";
    case "LOW": return "text-indigo-400";
    case "SPECULATIVE": return "text-purple-400";
    default: return "text-gray-500";
  }
}

export function confidenceDot(level: string | null) {
  switch (level) {
    case "HIGH": return "bg-emerald-400";
    case "MODERATE": return "bg-amber-400";
    case "LOW": return "bg-indigo-400";
    default: return "bg-gray-600";
  }
}
