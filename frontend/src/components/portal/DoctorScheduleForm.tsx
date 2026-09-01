"use client";

import { useState } from "react";
import { Copy, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type TimeRange = { start: string; end: string };

export type DoctorScheduleFormState = {
  department_id: string;
  name: string;
  specialization: string;
  qualification: string;
  years_experience: string;
  working_days: string[];
  shifts: TimeRange[];
  breaks: TimeRange[];
  slot_duration_minutes: string;
  max_bookings_per_slot: string;
  daily_booking_limit: string;
  online_quota: string;
  walkin_quota: string;
  followup_duration_minutes: string;
  effective_from: string;
};

export function emptyDoctorScheduleForm(): DoctorScheduleFormState {
  return {
    department_id: "",
    name: "",
    specialization: "",
    qualification: "",
    years_experience: "",
    working_days: [],
    shifts: [{ start: "", end: "" }],
    breaks: [],
    slot_duration_minutes: "",
    max_bookings_per_slot: "1",
    daily_booking_limit: "",
    online_quota: "",
    walkin_quota: "",
    followup_duration_minutes: "",
    effective_from: "",
  };
}

type Department = { id: string; name: string };

type Props = {
  departments: Department[];
  value: DoctorScheduleFormState;
  onChange: (next: DoctorScheduleFormState) => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
  errors: string[];
};

export function DoctorScheduleForm({ departments, value, onChange, onSave, onCancel, saving, errors }: Props) {
  const [showCopyDays, setShowCopyDays] = useState(false);

  function set<K extends keyof DoctorScheduleFormState>(key: K, val: DoctorScheduleFormState[K]) {
    onChange({ ...value, [key]: val });
  }

  function toggleDay(day: string) {
    set(
      "working_days",
      value.working_days.includes(day) ? value.working_days.filter((d) => d !== day) : [...value.working_days, day],
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
    set("shifts", value.shifts.filter((_, idx) => idx !== i));
    if (value.breaks[i]) set("breaks", value.breaks.filter((_, idx) => idx !== i));
  }

  function setBreak(i: number, range: TimeRange) {
    const breaks = [...value.breaks];
    breaks[i] = range;
    set("breaks", breaks);
  }

  const initial = value.name.trim().charAt(0).toUpperCase() || "?";

  return (
    <Card className="p-space-5">
      <div className="mb-space-5 flex flex-wrap items-start justify-between gap-space-3">
        <div className="flex items-center gap-space-3">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[20px] font-bold text-brand-700">
            {initial}
          </div>
          <div className="grid grid-cols-1 gap-space-2 md:grid-cols-2">
            <Input placeholder="Doctor name" value={value.name} onChange={(e) => set("name", e.target.value)} />
            <Input
              placeholder="Specialization"
              value={value.specialization}
              onChange={(e) => set("specialization", e.target.value)}
            />
          </div>
        </div>
        <div className="flex gap-space-2">
          <Button
            type="button"
            variant="secondary"
            size="md"
            onClick={() => setShowCopyDays((v) => !v)}
          >
            <Copy size={14} /> Copy to other days
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-x-space-4 md:grid-cols-3">
        <Field label="Department" htmlFor="doctor_department" required>
          <select
            id="doctor_department"
            required
            value={value.department_id}
            onChange={(e) => set("department_id", e.target.value)}
            className="h-11 w-full rounded-md border border-line bg-card px-space-3 text-[14px] text-ink-900"
          >
            <option value="">Choose…</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Qualification" htmlFor="doctor_qualification">
          <Input id="doctor_qualification" value={value.qualification} onChange={(e) => set("qualification", e.target.value)} />
        </Field>
        <Field label="Years experience" htmlFor="doctor_years">
          <Input
            id="doctor_years"
            type="number"
            min={0}
            value={value.years_experience}
            onChange={(e) => set("years_experience", e.target.value)}
          />
        </Field>
      </div>

      <Field label="Working days">
        <div className="flex flex-wrap items-center gap-space-2">
          {WEEKDAYS.map((day) => {
            const on = value.working_days.includes(day);
            return (
              <button
                key={day}
                type="button"
                onClick={() => toggleDay(day)}
                className={cn(
                  "flex h-9 w-14 items-center justify-center rounded-md border text-[12.5px] font-semibold transition-colors duration-150",
                  on ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-card text-ink-600 hover:border-brand-300",
                )}
              >
                {day}
              </button>
            );
          })}
          <button type="button" onClick={selectWeekdays} className="ml-space-2 text-[12.5px] font-semibold text-brand-600 hover:underline">
            Select weekdays
          </button>
        </div>
        {showCopyDays && (
          <p className="text-hint mt-space-1">
            "Copy to other days" just means selecting more day pills above — every shift/break already applies uniformly
            to every checked day.
          </p>
        )}
      </Field>

      <Field label="Shifts">
        <div className="space-y-space-2">
          {value.shifts.map((shift, i) => (
            <div key={i} className="flex flex-wrap items-center gap-space-2 rounded-lg border border-line bg-paper p-space-3">
              <span className="w-14 shrink-0 text-[12.5px] font-semibold text-ink-600">Shift {i + 1}</span>
              <Input type="time" value={shift.start} onChange={(e) => setShift(i, { ...shift, start: e.target.value })} className="w-32" />
              <span className="text-[12.5px] text-ink-400">to</span>
              <Input type="time" value={shift.end} onChange={(e) => setShift(i, { ...shift, end: e.target.value })} className="w-32" />

              <span className="ml-space-3 w-12 shrink-0 text-[12.5px] font-semibold text-ink-600">Break</span>
              <Input
                type="time"
                value={value.breaks[i]?.start || ""}
                onChange={(e) => setBreak(i, { start: e.target.value, end: value.breaks[i]?.end || "" })}
                className="w-32"
              />
              <span className="text-[12.5px] text-ink-400">to</span>
              <Input
                type="time"
                value={value.breaks[i]?.end || ""}
                onChange={(e) => setBreak(i, { start: value.breaks[i]?.start || "", end: e.target.value })}
                className="w-32"
              />

              {value.shifts.length > 1 && (
                <button type="button" onClick={() => removeShift(i)} className="ml-auto shrink-0 text-ink-400 hover:text-error">
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          ))}
          <button type="button" onClick={addShift} className="flex items-center gap-1 text-[12.5px] font-semibold text-brand-600 hover:underline">
            <Plus size={13} /> Add another shift
          </button>
        </div>
      </Field>

      <div className="grid grid-cols-1 gap-x-space-4 md:grid-cols-3">
        <Field label="Slot duration" htmlFor="slot_duration" hint="minutes">
          <Input id="slot_duration" type="number" min={1} value={value.slot_duration_minutes} onChange={(e) => set("slot_duration_minutes", e.target.value)} />
        </Field>
        <Field label="Max bookings" htmlFor="max_bookings" hint="per slot">
          <Input id="max_bookings" type="number" min={1} value={value.max_bookings_per_slot} onChange={(e) => set("max_bookings_per_slot", e.target.value)} />
        </Field>
        <Field label="Daily limit" htmlFor="daily_limit" hint="optional">
          <Input id="daily_limit" type="number" min={0} value={value.daily_booking_limit} onChange={(e) => set("daily_booking_limit", e.target.value)} />
        </Field>
        <Field label="Online quota" htmlFor="online_quota" hint="optional">
          <Input id="online_quota" type="number" min={0} value={value.online_quota} onChange={(e) => set("online_quota", e.target.value)} />
        </Field>
        <Field label="Walk-in quota" htmlFor="walkin_quota" hint="optional">
          <Input id="walkin_quota" type="number" min={0} value={value.walkin_quota} onChange={(e) => set("walkin_quota", e.target.value)} />
        </Field>
        <Field label="Follow-up duration" htmlFor="followup_duration" hint="minutes, optional">
          <Input id="followup_duration" type="number" min={1} value={value.followup_duration_minutes} onChange={(e) => set("followup_duration_minutes", e.target.value)} />
        </Field>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-space-3">
        <Field label="Effective from" htmlFor="effective_from" hint="optional — blank means immediately" className="mb-0 max-w-[220px]">
          <Input id="effective_from" type="date" value={value.effective_from} onChange={(e) => set("effective_from", e.target.value)} />
        </Field>
        <div className="mb-space-4 flex gap-space-2">
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" onClick={onSave} disabled={saving}>
            {saving ? "Saving…" : "Save schedule"}
          </Button>
        </div>
      </div>

      {errors.length > 0 && (
        <div className="rounded-md border border-error bg-error-tint p-space-3 text-[12.5px] text-error">
          <ul className="list-disc pl-space-4">
            {errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
