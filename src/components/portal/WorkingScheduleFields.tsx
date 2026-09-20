"use client";

import { Plus, Trash2 } from "lucide-react";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export type TimeRange = { start: string; end: string };

export type WorkingScheduleValue = {
  working_days: string[];
  shifts: TimeRange[];
  breaks: TimeRange[];
};

type Props = {
  value: WorkingScheduleValue;
  onChange: (next: WorkingScheduleValue) => void;
};

/** "Working days" day-pills + "Shifts" time/break row list, shared by both
 * Doctors and Staff add/edit forms. Used to also have a "Copy to other
 * days" button here -- removed (confirmed with the user) since it was
 * dead UI: every shift/break already applies uniformly to every checked
 * working day, so there was never anything to actually copy; the button
 * only opened a hint admitting exactly that. */
export function WorkingScheduleFields({ value, onChange }: Props) {
  function set<K extends keyof WorkingScheduleValue>(key: K, val: WorkingScheduleValue[K]) {
    onChange({ ...value, [key]: val });
  }

  function toggleDay(day: string) {
    set(
      "working_days",
      value.working_days.includes(day)
        ? value.working_days.filter((d) => d !== day)
        : [...value.working_days, day],
    );
  }

  function selectWeekdays() {
    const next = new Set(value.working_days);
    ["Mon", "Tue", "Wed", "Thu", "Fri"].forEach((d) => next.add(d));
    set("working_days", Array.from(next));
  }

  function setShift(i: number, range: TimeRange) {
    const shifts = [...value.shifts];
    shifts[i] = range;
    set("shifts", shifts);
  }
  function addShift() {
    set("shifts", [...value.shifts, { start: "", end: "" }]);
  }
  function removeShift(i: number) {
    set(
      "shifts",
      value.shifts.filter((_, idx) => idx !== i),
    );
    if (value.breaks[i])
      set(
        "breaks",
        value.breaks.filter((_, idx) => idx !== i),
      );
  }

  function setBreak(i: number, range: TimeRange) {
    const breaks = [...value.breaks];
    breaks[i] = range;
    set("breaks", breaks);
  }

  return (
    <>
      <p className="mb-space-1 text-label">Working days</p>
      <Field>
        <div className="gap-space-2 flex flex-wrap items-center">
          {WEEKDAYS.map((day) => {
            const on = value.working_days.includes(day);
            return (
              <button
                key={day}
                type="button"
                onClick={() => toggleDay(day)}
                className={cn(
                  "flex h-9 w-14 items-center justify-center rounded-md border text-[12.5px] font-semibold transition-colors duration-150",
                  on
                    ? "border-brand-600 bg-brand-600 text-white"
                    : "border-line bg-card text-ink-600 hover:border-brand-300",
                )}
              >
                {day}
              </button>
            );
          })}
          <button
            type="button"
            onClick={selectWeekdays}
            className="ml-space-2 text-brand-600 text-[12.5px] font-semibold hover:underline"
          >
            Select weekdays
          </button>
        </div>
      </Field>

      <Field
        label="Shifts"
        hint="Break is optional -- leave both times blank if this shift has none."
      >
        <div className="space-y-space-2">
          {value.shifts.map((shift, i) => (
            <div key={i} className="border-line bg-paper p-space-3 rounded-lg border">
              <div className="mb-space-2 gap-space-2 flex items-center justify-between">
                <span className="text-ink-600 text-[12.5px] font-semibold">Shift {i + 1}</span>
                {value.shifts.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeShift(i)}
                    className="text-ink-400 hover:text-error shrink-0"
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
              <div className="gap-space-2 flex flex-wrap items-center">
                <span className="text-ink-400 w-12 shrink-0 text-[12.5px]">Working</span>
                <Input
                  type="time"
                  value={shift.start}
                  onChange={(e) => setShift(i, { ...shift, start: e.target.value })}
                  className="w-32"
                />
                <span className="text-ink-400 text-[12.5px]">to</span>
                <Input
                  type="time"
                  value={shift.end}
                  onChange={(e) => setShift(i, { ...shift, end: e.target.value })}
                  className="w-32"
                />
              </div>
              <div className="mt-space-2 gap-space-2 flex flex-wrap items-center">
                <span className="text-ink-400 w-12 shrink-0 text-[12.5px]">Break</span>
                <Input
                  type="time"
                  value={value.breaks[i]?.start || ""}
                  onChange={(e) =>
                    setBreak(i, { start: e.target.value, end: value.breaks[i]?.end || "" })
                  }
                  className="w-32"
                />
                <span className="text-ink-400 text-[12.5px]">to</span>
                <Input
                  type="time"
                  value={value.breaks[i]?.end || ""}
                  onChange={(e) =>
                    setBreak(i, { start: value.breaks[i]?.start || "", end: e.target.value })
                  }
                  className="w-32"
                />
              </div>
            </div>
          ))}
          <button
            type="button"
            onClick={addShift}
            className="text-brand-600 flex items-center gap-1 text-[12.5px] font-semibold hover:underline"
          >
            <Plus size={13} /> Add another shift
          </button>
        </div>
      </Field>
    </>
  );
}
