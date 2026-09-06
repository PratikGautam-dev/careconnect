"use client";

import { cn } from "@/lib/cn";

type SwitchSize = "sm" | "md";

const trackSizes: Record<SwitchSize, string> = {
  sm: "h-5 w-9",
  md: "h-6 w-11",
};

const thumbSizes: Record<SwitchSize, string> = {
  sm: "h-4 w-4",
  md: "h-5 w-5",
};

const thumbOnTranslate: Record<SwitchSize, string> = {
  sm: "translate-x-[18px]",
  md: "translate-x-[22px]",
};

type SwitchProps = {
  checked: boolean;
  onChange: () => void;
  disabled?: boolean;
  size?: SwitchSize;
  className?: string;
  "aria-label"?: string;
};

/** Shared on/off toggle -- replaces the hand-rolled `role="switch"` button
 * that used to be copy-pasted (with tiny drifting inconsistencies) across
 * doctor/staff active-toggles, appointment types, and diagnostic managers. */
export function Switch({ checked, onChange, disabled, size = "md", className, ...rest }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={onChange}
      className={cn(
        "relative shrink-0 rounded-full shadow-inner transition-colors duration-150",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        trackSizes[size],
        checked ? "bg-brand-600 hover:bg-brand-700" : "bg-line hover:bg-black/15",
        className,
      )}
      {...rest}
    >
      <span
        className={cn(
          "absolute top-0.5 left-0.5 rounded-full bg-white shadow-[var(--shadow-sm)] transition-transform duration-150",
          thumbSizes[size],
          checked && thumbOnTranslate[size],
        )}
      />
    </button>
  );
}
