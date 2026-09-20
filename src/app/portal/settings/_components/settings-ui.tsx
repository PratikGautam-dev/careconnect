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
  icon: Icon,
  tint,
  title,
  subtitle,
}: {
  icon: LucideIcon;
  tint: Tint;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="mb-space-4 gap-space-3 flex items-start">
      <span
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-md",
          TINT_CLASSES[tint],
        )}
      >
        <Icon size={17} strokeWidth={2} />
      </span>
      <div className="min-w-0">
        <h3 className="text-ink-900 text-[14px] font-bold">{title}</h3>
        <p className="text-hint">{subtitle}</p>
      </div>
    </div>
  );
}

export function Select({
  value,
  onChange,
  options,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
  disabled?: boolean;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px] disabled:cursor-not-allowed disabled:opacity-50"
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

/** Like Select above, but for a fixed list of numeric options with a unit
 * suffix (e.g. "30 minutes") -- General and Appointments tabs both use this
 * for their NumberSelect-backed settings fields (session timeout, slot
 * duration, buffer time, advance booking limit, ...). */
export function NumberSelect({
  value,
  onChange,
  options,
  suffix,
  disabled,
}: {
  value: number;
  onChange: (v: number) => void;
  options: number[];
  suffix: string;
  disabled?: boolean;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      disabled={disabled}
      className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px] disabled:cursor-not-allowed disabled:opacity-50"
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o} {suffix}
        </option>
      ))}
    </select>
  );
}

/** A real, already-persisted value (e.g. from usePortalSettings) may not be
 * one of a NumberSelect's preset dropdown options -- ensures it's selectable
 * (shown in place, sorted in) instead of silently mismatching the <select>. */
export function withValue(options: number[], value: number): number[] {
  return options.includes(value) ? options : [...options, value].sort((a, b) => a - b);
}

export function ToggleRow({
  label,
  subtitle,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  subtitle: string;
  checked: boolean;
  onChange: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="gap-space-3 py-space-2 flex items-center justify-between">
      <div className="min-w-0">
        <p className="text-ink-900 text-[13px] font-semibold">{label}</p>
        <p className="text-hint truncate">{subtitle}</p>
      </div>
      <Switch checked={checked} onChange={onChange} disabled={disabled} />
    </div>
  );
}
