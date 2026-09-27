"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";

// Same underlying contract usePortalSettings/the backend already use --
// reminder_offsets_hours stays a plain comma-separated-hours string end to
// end (portal/routes/settings.py parses/serializes it, admin/validation.py's
// _parse_offsets is the lenient source of truth for what's actually valid).
// This component only changes how a human edits that string: pick "N days
// before" / "N hours before" pills instead of typing "72,24,6,1" by hand.

const PRESET_HOURS = [72, 48, 24, 6, 3, 1];

function parseOffsets(text: string): number[] {
  const values = (text || "")
    .split(",")
    .map((s) => Number(s.trim()))
    .filter((n) => Number.isFinite(n) && n > 0);
  return Array.from(new Set(values)).sort((a, b) => b - a);
}

function serializeOffsets(hours: number[]): string {
  return Array.from(new Set(hours))
    .sort((a, b) => b - a)
    .join(",");
}

function formatOffsetUnit(hours: number): string {
  if (hours >= 24 && hours % 24 === 0) {
    const days = hours / 24;
    return `${days} day${days === 1 ? "" : "s"}`;
  }
  const rounded = Number.isInteger(hours) ? hours : Math.round(hours * 10) / 10;
  return `${rounded} hour${rounded === 1 ? "" : "s"}`;
}

function formatOffsetLabel(hours: number): string {
  return `${formatOffsetUnit(hours)} before`;
}

// "1 day, 6 hours and 1 hour" -- standard English list join (comma between
// all but the last pair, "and" before the last) so the summary sentence
// reads naturally regardless of how many offsets are selected.
function joinWithAnd(parts: string[]): string {
  if (parts.length <= 1) return parts.join("");
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

type Props = {
  value: string;
  onChange: (next: string) => void;
  error?: string | null;
};

/** Friendlier replacement for the raw "comma-separated hours" text input --
 * one reminder per pill, in plain "N days/hours before" language, plus a
 * small custom-add row for an offset none of the presets cover. Reading a
 * pill row back is meant to be self-explanatory even with a mixed list like
 * [72, 24, 6, 1] ("3 days before", "1 day before", "6 hours before",
 * "1 hour before") -- the exact "1 day AND 2 day AND ... AND 2,3,6 hours"
 * combination this replaces a confusing raw string for. */
export function ReminderOffsetsField({ value, onChange, error }: Props) {
  const selected = parseOffsets(value);
  const [customAmount, setCustomAmount] = useState("");
  const [customUnit, setCustomUnit] = useState<"hours" | "days">("hours");

  function toggle(hours: number) {
    const next = selected.includes(hours)
      ? selected.filter((h) => h !== hours)
      : [...selected, hours];
    onChange(serializeOffsets(next));
  }

  function remove(hours: number) {
    onChange(serializeOffsets(selected.filter((h) => h !== hours)));
  }

  function addCustom() {
    const amount = Number(customAmount);
    if (!Number.isFinite(amount) || amount <= 0) return;
    const hours = customUnit === "days" ? amount * 24 : amount;
    onChange(serializeOffsets([...selected, hours]));
    setCustomAmount("");
  }

  // Presets not already covered by the current selection (an exact-value
  // custom addition, e.g. 5 hours, still shows as its own pill above even
  // though it's not one of these).
  const extraSelected = selected.filter((h) => !PRESET_HOURS.includes(h));

  return (
    <Field
      label="Appointment reminders"
      className="mb-0 sm:col-span-2"
      error={error || undefined}
      hint={
        error
          ? undefined
          : "Choose when a WhatsApp reminder should go out before each appointment. Pick as many as you like."
      }
    >
      <div className="gap-space-2 flex flex-wrap items-center">
        {[...PRESET_HOURS, ...extraSelected]
          .sort((a, b) => b - a)
          .map((hours) => {
            const on = selected.includes(hours);
            return (
              <button
                key={hours}
                type="button"
                onClick={() => toggle(hours)}
                className={cn(
                  "px-space-3 gap-space-1 flex h-9 items-center rounded-full border text-[12.5px] font-semibold transition-colors duration-150",
                  on
                    ? "border-brand-600 bg-brand-600 text-white"
                    : "border-line bg-card text-ink-600 hover:border-brand-300",
                )}
              >
                {formatOffsetLabel(hours)}
                {on && (
                  <X
                    size={12}
                    strokeWidth={2.5}
                    onClick={(e) => {
                      e.stopPropagation();
                      remove(hours);
                    }}
                  />
                )}
              </button>
            );
          })}
      </div>

      <p className="mt-space-2 text-ink-900 text-[12.5px]">
        {selected.length === 0 ? (
          <span className="text-ink-400">No reminders selected -- pick at least one above.</span>
        ) : (
          <>
            A reminder will be sent{" "}
            <span className="font-bold">
              {joinWithAnd(selected.map((h) => formatOffsetUnit(h)))}
            </span>{" "}
            before the appointment.
          </>
        )}
      </p>

      <div className="mt-space-2 gap-space-2 flex flex-wrap items-center">
        <Input
          type="number"
          min={1}
          placeholder="e.g. 5"
          value={customAmount}
          onChange={(e) => setCustomAmount(e.target.value)}
          className="w-24"
        />
        <select
          value={customUnit}
          onChange={(e) => setCustomUnit(e.target.value as "hours" | "days")}
          className="border-line bg-card text-ink-600 h-9 rounded-md border px-2 text-[12.5px]"
        >
          <option value="hours">Hours before</option>
          <option value="days">Days before</option>
        </select>
        <button
          type="button"
          onClick={addCustom}
          disabled={!customAmount}
          className="text-brand-600 text-[12.5px] font-semibold hover:underline disabled:opacity-40"
        >
          Add
        </button>
      </div>
    </Field>
  );
}
