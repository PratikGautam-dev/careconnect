import { Plus, Trash2, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { DoctorForm, WEEKDAYS } from "../types";
import type { WizardDispatch } from "../useWizardState";

type Props = {
  deptIndex: number;
  docIndex: number;
  doctor: DoctorForm;
  dispatch: WizardDispatch;
  /** Clinics have exactly one doctor -- hide the per-card "Doctor #N" /
   * Remove affordances that only make sense in a multi-doctor repeater. */
  hideActions?: boolean;
};

export function DoctorCard({ deptIndex, docIndex, doctor, dispatch, hideActions }: Props) {
  const set = (field: keyof DoctorForm, value: unknown) =>
    dispatch({ type: "setDoctorField", deptIndex, docIndex, field, value });

  return (
    <div className="rounded-lg border border-line bg-paper p-space-4">
      {!hideActions && (
        <div className="mb-space-3 flex items-center justify-between">
          <strong className="text-[13.5px] font-bold text-ink-900">Doctor #{docIndex + 1}</strong>
          <button
            type="button"
            onClick={() => dispatch({ type: "removeDoctor", deptIndex, docIndex })}
            className="flex items-center gap-1 text-[12.5px] font-semibold text-error hover:underline"
          >
            <Trash2 size={13} /> Remove
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
        <Field label="Name" htmlFor={`doc-${deptIndex}-${docIndex}-name`}>
          <Input id={`doc-${deptIndex}-${docIndex}-name`} value={doctor.name} onChange={(e) => set("name", e.target.value)} />
        </Field>
        <Field label="Specialization" htmlFor={`doc-${deptIndex}-${docIndex}-spec`}>
          <Input
            id={`doc-${deptIndex}-${docIndex}-spec`}
            value={doctor.specialization}
            onChange={(e) => set("specialization", e.target.value)}
          />
        </Field>
        <Field label="Qualification" htmlFor={`doc-${deptIndex}-${docIndex}-qual`}>
          <Input
            id={`doc-${deptIndex}-${docIndex}-qual`}
            value={doctor.qualification}
            onChange={(e) => set("qualification", e.target.value)}
          />
        </Field>
        <Field label="Years experience" htmlFor={`doc-${deptIndex}-${docIndex}-years`}>
          <Input
            id={`doc-${deptIndex}-${docIndex}-years`}
            type="number"
            min={0}
            value={doctor.yearsExperience}
            onChange={(e) => set("yearsExperience", e.target.value)}
          />
        </Field>
      </div>

      <Field label="Working days">
        <div className="flex flex-wrap items-center gap-space-2">
          {WEEKDAYS.map((day) => {
            const on = doctor.workingDays.includes(day);
            return (
              <button
                key={day}
                type="button"
                onClick={() => dispatch({ type: "toggleDoctorDay", deptIndex, docIndex, day })}
                className={cn(
                  "flex h-8 w-11 items-center justify-center rounded-md border text-[12.5px] font-semibold transition-colors duration-150",
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
            onClick={() => dispatch({ type: "selectAllWeekdays", deptIndex, docIndex })}
            className="ml-space-2 text-[12.5px] font-semibold text-brand-600 hover:underline"
          >
            Select all weekdays
          </button>
        </div>
      </Field>

      <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
        <Field label="Working hours" hint="Add another row for a split shift (e.g. morning + evening).">
          <div className="space-y-space-2">
            {doctor.shifts.map((shift, i) => (
              <div key={i} className="flex items-center gap-space-2">
                <Input
                  type="time"
                  value={shift.start}
                  onChange={(e) =>
                    dispatch({ type: "setShift", deptIndex, docIndex, shiftIndex: i, range: { ...shift, start: e.target.value } })
                  }
                />
                <span className="text-[12.5px] text-ink-400">to</span>
                <Input
                  type="time"
                  value={shift.end}
                  onChange={(e) =>
                    dispatch({ type: "setShift", deptIndex, docIndex, shiftIndex: i, range: { ...shift, end: e.target.value } })
                  }
                />
                {doctor.shifts.length > 1 && (
                  <button
                    type="button"
                    onClick={() => dispatch({ type: "removeShift", deptIndex, docIndex, shiftIndex: i })}
                    className="shrink-0 text-ink-400 hover:text-error"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>
            ))}
            <button
              type="button"
              onClick={() => dispatch({ type: "addShift", deptIndex, docIndex })}
              className="flex items-center gap-1 text-[12.5px] font-semibold text-brand-600 hover:underline"
            >
              <Plus size={13} /> Add another shift
            </button>
          </div>
        </Field>
        <Field
          label="Slot duration (minutes)"
          htmlFor={`doc-${deptIndex}-${docIndex}-duration`}
          hint="How long each appointment lasts — e.g. 20 means a new slot every 20 minutes."
        >
          <Input
            id={`doc-${deptIndex}-${docIndex}-duration`}
            type="number"
            min={1}
            value={doctor.slotDurationMinutes}
            onChange={(e) => set("slotDurationMinutes", e.target.value)}
          />
        </Field>
      </div>

      <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
        <Field label="Breaks (optional)" hint="Excluded from bookable slots within whichever shift it falls in.">
          <div className="space-y-space-2">
            {doctor.breaks.map((brk, i) => (
              <div key={i} className="flex items-center gap-space-2">
                <Input
                  type="time"
                  value={brk.start}
                  onChange={(e) =>
                    dispatch({ type: "setBreak", deptIndex, docIndex, breakIndex: i, range: { ...brk, start: e.target.value } })
                  }
                />
                <span className="text-[12.5px] text-ink-400">to</span>
                <Input
                  type="time"
                  value={brk.end}
                  onChange={(e) =>
                    dispatch({ type: "setBreak", deptIndex, docIndex, breakIndex: i, range: { ...brk, end: e.target.value } })
                  }
                />
                <button
                  type="button"
                  onClick={() => dispatch({ type: "removeBreak", deptIndex, docIndex, breakIndex: i })}
                  className="shrink-0 text-ink-400 hover:text-error"
                >
                  <X size={16} />
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => dispatch({ type: "addBreak", deptIndex, docIndex })}
              className="flex items-center gap-1 text-[12.5px] font-semibold text-brand-600 hover:underline"
            >
              <Plus size={13} /> Add a break
            </button>
          </div>
        </Field>
        <Field
          label="Follow-up duration (minutes, optional)"
          htmlFor={`doc-${deptIndex}-${docIndex}-followup`}
          hint="A separate, usually shorter, slot length for follow-up visits."
        >
          <Input
            id={`doc-${deptIndex}-${docIndex}-followup`}
            type="number"
            min={1}
            value={doctor.followupDurationMinutes}
            onChange={(e) => set("followupDurationMinutes", e.target.value)}
          />
        </Field>
      </div>

      <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
        <Field
          label="Bookings per slot"
          htmlFor={`doc-${deptIndex}-${docIndex}-max`}
          hint="How many patients can book the exact same slot time."
        >
          <Input
            id={`doc-${deptIndex}-${docIndex}-max`}
            type="number"
            min={1}
            value={doctor.maxBookingsPerSlot}
            onChange={(e) => set("maxBookingsPerSlot", e.target.value)}
          />
        </Field>
        <Field
          label="Daily booking limit (optional)"
          htmlFor={`doc-${deptIndex}-${docIndex}-daily`}
          hint="Caps total bookings per day, regardless of how many slots exist."
        >
          <Input
            id={`doc-${deptIndex}-${docIndex}-daily`}
            type="number"
            min={0}
            value={doctor.dailyBookingLimit}
            onChange={(e) => set("dailyBookingLimit", e.target.value)}
          />
        </Field>
      </div>

      <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
        <Field label="Online quota (optional)" htmlFor={`doc-${deptIndex}-${docIndex}-online`}>
          <Input
            id={`doc-${deptIndex}-${docIndex}-online`}
            type="number"
            min={0}
            value={doctor.onlineQuota}
            onChange={(e) => set("onlineQuota", e.target.value)}
          />
        </Field>
        <Field
          label="Walk-in quota (optional)"
          htmlFor={`doc-${deptIndex}-${docIndex}-walkin`}
          hint="Reserved split between WhatsApp and front-desk bookings."
        >
          <Input
            id={`doc-${deptIndex}-${docIndex}-walkin`}
            type="number"
            min={0}
            value={doctor.walkinQuota}
            onChange={(e) => set("walkinQuota", e.target.value)}
          />
        </Field>
      </div>

      <Field
        label="Schedule effective from (optional)"
        htmlFor={`doc-${deptIndex}-${docIndex}-effective`}
        hint="Leave blank for effective immediately."
        className="mb-0 sm:w-1/2 sm:pr-space-2"
      >
        <Input
          id={`doc-${deptIndex}-${docIndex}-effective`}
          type="date"
          value={doctor.effectiveFrom}
          onChange={(e) => set("effectiveFrom", e.target.value)}
        />
      </Field>
    </div>
  );
}
