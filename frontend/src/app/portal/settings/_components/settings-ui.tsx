"use client";

import type { LucideIcon } from "lucide-react";
import { Switch } from "@/components/ui/Switch";
import { cn } from "@/lib/cn";

// Small shared pieces used by more than one /portal/settings tab (General,
// Hospital Profile, ...) so each tab file doesn't redefine its own copy.

export type Tint = "brand" | "success" | "error" | "clay";

export const TINT_CLASSES: Record<Tint, string> = {
  brand: "bg-brand-50 text-brand-600",
  success: "bg-success-tint text-success",
  error: "bg-error-tint text-error",
  clay: "bg-clay-100 text-clay-700",
};

export function SectionHeader({
  icon: Icon, tint, title, subtitle,
}: { icon: LucideIcon; tint: Tint; title: string; subtitle: string }) {
  return (
    <div className="mb-space-4 flex items-start gap-space-3">
      <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-md", TINT_CLASSES[tint])}>
        <Icon size={17} strokeWidth={2} />
      </span>
      <div className="min-w-0">
        <h3 className="text-[14px] font-bold text-ink-900">{title}</h3>
        <p className="text-hint">{subtitle}</p>
      </div>
    </div>
  );
}

export function Select({
  value, onChange, options, disabled,
}: { value: string; onChange: (v: string) => void; options: string[]; disabled?: boolean }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13.5px] text-ink-900 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {options.map((o) => (
        <option key={o} value={o}>{o}</option>
      ))}
    </select>
  );
}

export function ToggleRow({
  label, subtitle, checked, onChange, disabled,
}: { label: string; subtitle: string; checked: boolean; onChange: () => void; disabled?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-space-3 py-space-2">
      <div className="min-w-0">
        <p className="text-[13px] font-semibold text-ink-900">{label}</p>
        <p className="text-hint truncate">{subtitle}</p>
      </div>
      <Switch checked={checked} onChange={onChange} disabled={disabled} />
    </div>
  );
}
