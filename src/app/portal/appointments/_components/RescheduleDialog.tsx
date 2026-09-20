"use client";

import { CalendarClock, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { cn } from "@/lib/cn";
import type { Appointment, SlotsByDate } from "@/hooks/useAppointments";

type RescheduleDialogProps = {
  appointment: Appointment | null;
  onOpenChange: (open: boolean) => void;
  slotsByDate: SlotsByDate | null;
  message: string;
  setMessage: (v: string) => void;
  errors: string[];
  submitting: boolean;
  date: string;
  setDate: (v: string) => void;
  slotId: string;
  setSlotId: (v: string) => void;
  datesForDoctor: string[];
  slotsForDate: { id: string; label: string }[];
  onSubmit: () => void;
};

/** Reschedule as a dialog, not an inline expanding row -- only date/slot are
 * pickable here. Department/doctor (or, for a diagnostic/lab booking with no
 * doctor at all, the resource) stay whatever the appointment already has
 * (shown read-only below) rather than a dropdown -- rescheduling moves an
 * appointment's time, not who/what it's with. */
export function RescheduleDialog({
  appointment,
  onOpenChange,
  slotsByDate,
  message,
  setMessage,
  errors,
  submitting,
  date,
  setDate,
  slotId,
  setSlotId,
  datesForDoctor,
  slotsForDate,
  onSubmit,
}: RescheduleDialogProps) {
  const open = appointment !== null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogTitle>Reschedule appointment</DialogTitle>

        {!appointment ? null : (
          <>
            <div className="mb-space-4 gap-x-space-4 grid grid-cols-1 md:grid-cols-2">
              <Field label="Department">
                <div className="border-line bg-paper px-space-3 text-ink-600 flex h-11 items-center rounded-md border text-[14px]">
                  {appointment.department_name || "—"}
                </div>
              </Field>
              <Field label={appointment.doctor_id ? "Doctor" : "Resource"}>
                <div className="border-line bg-paper px-space-3 text-ink-600 flex h-11 items-center rounded-md border text-[14px]">
                  {appointment.doctor_name || appointment.diagnostic_test_name || "—"}
                </div>
              </Field>
            </div>

            {!slotsByDate ? (
              <p className="text-ink-400 text-[13px]">Loading…</p>
            ) : (
              <>
                <Field label="Date" required>
                  {datesForDoctor.length === 0 ? (
                    <p className="text-ink-400 text-[12.5px]">
                      No available dates for this {appointment.doctor_id ? "doctor" : "resource"}.
                    </p>
                  ) : (
                    <div className="gap-space-2 flex flex-wrap">
                      {datesForDoctor.map((d) => (
                        <button
                          type="button"
                          key={d}
                          onClick={() => {
                            setDate(d);
                            setSlotId("");
                          }}
                          className={cn(
                            "px-space-3 py-space-2 rounded-md border text-[12.5px] font-semibold",
                            date === d
                              ? "border-brand-600 bg-brand-600 text-white"
                              : "border-line bg-card text-ink-600",
                          )}
                        >
                          {d}
                        </button>
                      ))}
                    </div>
                  )}
                </Field>

                {date && (
                  <Field label="Time slot" required>
                    {slotsForDate.length === 0 ? (
                      <p className="text-ink-400 text-[12.5px]">No slots available on this date.</p>
                    ) : (
                      <div className="gap-space-2 flex flex-wrap">
                        {slotsForDate.map((s) => (
                          <button
                            type="button"
                            key={s.id}
                            onClick={() => setSlotId(s.id)}
                            className={cn(
                              "px-space-3 py-space-2 rounded-md border text-[12.5px] font-semibold",
                              slotId === s.id
                                ? "border-brand-600 bg-brand-600 text-white"
                                : "border-line bg-card text-ink-600",
                            )}
                          >
                            {s.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </Field>
                )}
              </>
            )}

            <Field
              label={`Message to send ${appointment.phone} on WhatsApp (optional)`}
              htmlFor="reschedule_message"
            >
              <textarea
                id="reschedule_message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={2}
                className="border-line bg-card px-space-3 py-space-2 text-ink-900 focus:border-brand-400 h-16 w-full resize-none rounded-md border text-[13px] outline-none"
              />
            </Field>

            {errors.length > 0 && (
              <div className="mb-space-3 border-error bg-error-tint p-space-3 text-error rounded-md border text-[12.5px]">
                <ul className="pl-space-4 list-disc">
                  {errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="gap-space-2 flex">
              <Button onClick={onSubmit} disabled={submitting || !slotId}>
                <CalendarClock size={13} /> {submitting ? "Rescheduling…" : "Send & reschedule"}
              </Button>
              <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={submitting}>
                <X size={13} /> Dismiss
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
