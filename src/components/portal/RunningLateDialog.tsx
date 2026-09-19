"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";
import type { Doctor } from "@/hooks/useDoctors";

const SHIFT_PRESETS = [
  { label: "10 min", hours: 0, minutes: 10 },
  { label: "15 min", hours: 0, minutes: 15 },
  { label: "30 min", hours: 0, minutes: 30 },
  { label: "45 min", hours: 0, minutes: 45 },
  { label: "1h", hours: 1, minutes: 0 },
  { label: "1h 30m", hours: 1, minutes: 30 },
];

function todayStr(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function nowTimeStr(): string {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

type Props = {
  doctor: Doctor | null;
  onOpenChange: (open: boolean) => void;
};

/** Doctors page's admin-side "Running late" quick action -- staff-triggered
 * equivalent of the doctor's own self-service Running late? panel
 * (DoctorDashboardView), for a doctor who calls/messages in running behind
 * instead of logging into their own dashboard. Unlike that self-service
 * version (always "today, from right now"), this lets staff pick the date,
 * the cutoff time appointments must be at or after, and the shift itself --
 * e.g. "today, from 3:20 PM, push back 1h 10m" -- so a receptionist can log
 * a delay the doctor phoned in about even after the fact, or for a
 * specific point later in the day. Shifts every still-booked appointment
 * matching that date+cutoff forward by the chosen amount and notifies each
 * affected patient on WhatsApp. */
export function RunningLateDialog({ doctor, onOpenChange }: Props) {
  const [date, setDate] = useState(todayStr());
  const [fromTime, setFromTime] = useState(nowTimeStr());
  const [shiftHours, setShiftHours] = useState("0");
  const [shiftMinutes, setShiftMinutes] = useState("15");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (doctor) {
      setDate(todayStr());
      setFromTime(nowTimeStr());
      setShiftHours("0");
      setShiftMinutes("15");
      setError(null);
    }
  }, [doctor]);

  const totalMinutes = (Number(shiftHours) || 0) * 60 + (Number(shiftMinutes) || 0);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!doctor) return;
    if (!date || !fromTime || totalMinutes < 1) return;
    setSaving(true);
    setError(null);
    const result = await portalFetch(`/api/portal/doctors/${doctor.id}/delay`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date, from_time: fromTime, minutes: totalMinutes }),
    });
    setSaving(false);
    if (!result.ok) {
      if (!result.unauthorized) setError(result.error);
      return;
    }
    const delayed = result.data as { notified: number };
    toast.success(
      delayed.notified === 0
        ? "No matching appointments to shift."
        : `Shifted ${delayed.notified} appointment${delayed.notified === 1 ? "" : "s"} and notified ${
            delayed.notified === 1 ? "the patient" : "each patient"
          } on WhatsApp.`,
    );
    onOpenChange(false);
  }

  return (
    <Dialog open={doctor !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>{doctor ? `${doctor.name} is running late` : "Running late"}</DialogTitle>
        <form onSubmit={handleSubmit} className="mt-space-3">
          <p className="mb-space-3 text-ink-600 text-[12.5px]">
            Every still-confirmed appointment on the chosen date, at or after the cutoff time,
            shifts forward by the chosen amount -- each patient gets a WhatsApp message with their
            new time automatically.
          </p>

          <div className="mb-space-3 gap-space-3 grid grid-cols-2">
            <Field label="Date" htmlFor="delay_date">
              <Input
                id="delay_date"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
              />
            </Field>
            <Field label="From time" htmlFor="delay_from_time">
              <Input
                id="delay_from_time"
                type="time"
                value={fromTime}
                onChange={(e) => setFromTime(e.target.value)}
                required
              />
            </Field>
          </div>

          <p className="mb-space-1 text-ink-600 text-[12px] font-semibold">Shift by</p>
          <div className="mb-space-2 gap-space-2 flex flex-wrap items-center">
            {SHIFT_PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => {
                  setShiftHours(String(p.hours));
                  setShiftMinutes(String(p.minutes));
                }}
                className={cn(
                  "px-space-3 h-9 rounded-md border text-[12.5px] font-semibold transition-colors duration-150",
                  Number(shiftHours) === p.hours && Number(shiftMinutes) === p.minutes
                    ? "border-brand-600 bg-brand-600 text-white"
                    : "border-line bg-card text-ink-600 hover:border-brand-300",
                )}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className="mb-space-3 gap-space-2 flex items-center">
            <input
              type="number"
              min={0}
              max={12}
              value={shiftHours}
              onChange={(e) => setShiftHours(e.target.value)}
              aria-label="Shift hours"
              className="border-line bg-card px-space-2 text-ink-900 h-9 w-16 rounded-md border text-[13px]"
            />
            <span className="text-ink-400 text-[12.5px]">hr</span>
            <input
              type="number"
              min={0}
              max={59}
              value={shiftMinutes}
              onChange={(e) => setShiftMinutes(e.target.value)}
              aria-label="Shift minutes"
              className="border-line bg-card px-space-2 text-ink-900 h-9 w-16 rounded-md border text-[13px]"
            />
            <span className="text-ink-400 text-[12.5px]">min</span>
          </div>

          {error && <p className="mb-space-3 text-error text-[12.5px] font-medium">{error}</p>}
          <Button type="submit" disabled={saving || !date || !fromTime || totalMinutes < 1}>
            {saving ? "Updating…" : "Shift appointments"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
