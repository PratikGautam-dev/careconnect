import { cn } from "@/lib/cn";

export type FilterOption = { value: string; label: string };

type FilterSelectProps = {
  value: string;
  onChange: (value: string) => void;
  /** Options as an ordered list -- build this from a shared const/enum map
   * (e.g. `Object.entries(STATUS_LABELS).map(([value, label]) => ({ value,
   * label }))`) rather than hand-typing <option> tags, so a filter and the
   * pill/label it's filtering by can never drift apart. */
  options: FilterOption[];
  /** Label for the unfiltered "all" state, e.g. "All Departments". */
  allLabel: string;
  ariaLabel?: string;
  className?: string;
};

/** Shared small filter dropdown -- one visual pattern for every "All X" list
 * filter row across the portal (department/status/gender today; doctors'
 * availability filter and similar are meant to move onto this too), instead
 * of each page hand-rolling its own <select> classes. Not for a data-entry
 * form field (those keep using Field + a plain <select>, e.g. Settings). */
export function FilterSelect({ value, onChange, options, allLabel, ariaLabel, className }: FilterSelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label={ariaLabel ?? allLabel}
      className={cn("h-9 rounded-md border border-line bg-card px-space-2 text-[12.5px] text-ink-900", className)}
    >
      <option value="all">{allLabel}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
