"use client";

import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { SectionHeader } from "./SectionHeader";
import { WorkingScheduleFields, type TimeRange } from "./WorkingScheduleFields";

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
  phone: string;
  location: string;
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
    phone: "",
    location: "",
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
  function set<K extends keyof DoctorScheduleFormState>(key: K, val: DoctorScheduleFormState[K]) {
    onChange({ ...value, [key]: val });
  }

  const initial = value.name.trim().charAt(0).toUpperCase() || "?";

  return (
    <div>
      <SectionHeader
        title="Profile information"
        description="Who this doctor is and how patients/staff reach them -- shown on their profile card and appointment listings."
      />
      <div className="mb-space-5 flex items-center gap-space-3">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[20px] font-bold text-brand-700">
          {initial}
        </div>
        <div className="grid grid-cols-1 gap-space-2 md:grid-cols-2">
          <Input required placeholder="Doctor name" value={value.name} onChange={(e) => set("name", e.target.value)} />
          <Input
            required
            placeholder="Specialization *"
            value={value.specialization}
            onChange={(e) => set("specialization", e.target.value)}
          />
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
        <Field label="Qualification" htmlFor="doctor_qualification" required>
          <Input required id="doctor_qualification" value={value.qualification} onChange={(e) => set("qualification", e.target.value)} />
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
        <Field label="Phone" htmlFor="doctor_phone" required>
          <Input required id="doctor_phone" type="tel" value={value.phone} onChange={(e) => set("phone", e.target.value)} />
        </Field>
        <Field label="Location" htmlFor="doctor_location" hint="room/cabin, optional">
          <Input id="doctor_location" value={value.location} onChange={(e) => set("location", e.target.value)} />
        </Field>
      </div>

      <div className="mt-space-5 border-t border-line pt-space-4">
        <SectionHeader
          title="Schedule"
          description="Which days this doctor works, and their shift timings -- these generate the actual bookable slots patients see."
        />
        <WorkingScheduleFields
          value={{ working_days: value.working_days, shifts: value.shifts, breaks: value.breaks }}
          onChange={(next) => onChange({ ...value, ...next })}
        />
      </div>

      <div className="mt-space-5 border-t border-line pt-space-4">
        <SectionHeader
          title="Booking settings"
          description="How appointments are sliced within the schedule above, and any per-day caps on how many can be booked."
        />
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
      </div>

      <div className="mt-space-5 flex flex-wrap items-end justify-between gap-space-3 border-t border-line pt-space-4">
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
    </div>
  );
}
