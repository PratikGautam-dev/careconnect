"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { staffFetch } from "@/lib/staffAuth";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type DoctorSchedule = {
  id: string;
  name: string;
  specialization: string | null;
  working_days: string[];
  working_hours: string[];
  breaks: string[];
  slot_duration_minutes: number;
  effective_from: string | null;
};

type LeaveEntry = { id: number; date: string; reason: string | null };

type TimeRange = { start: string; end: string };

function parseRanges(values: string[]): TimeRange[] {
  return values.map((v) => {
    const [start, end] = v.split("-");
    return { start: start || "", end: end || "" };
  });
}
function serializeRanges(ranges: TimeRange[]): string[] {
  return ranges.filter((r) => r.start && r.end).map((r) => `${r.start}-${r.end}`);
}

/** A doctor's own self-service schedule/leave editor -- shared by the
 * doctor's "Schedule" nav item under /portal and the legacy (unrouted)
 * /doctor/schedule page. Self-fetches /api/doctor/schedule + /api/doctor/leave;
 * the caller owns auth/guard/shell. */
export function DoctorScheduleView() {
  const router = useRouter();

  const [schedule, setSchedule] = useState<DoctorSchedule | null>(null);
  const [leave, setLeave] = useState<LeaveEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [workingDays, setWorkingDays] = useState<string[]>([]);
  const [shifts, setShifts] = useState<TimeRange[]>([{ start: "", end: "" }]);
  const [breaks, setBreaks] = useState<TimeRange[]>([]);
  const [slotDuration, setSlotDuration] = useState("30");
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [leaveDate, setLeaveDate] = useState("");
  const [leaveReason, setLeaveReason] = useState("");
  const [addingLeave, setAddingLeave] = useState(false);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/doctor/schedule");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    const data = result.data as { doctor: DoctorSchedule; leave: LeaveEntry[] };
    setSchedule(data.doctor);
    setLeave(data.leave);
    setWorkingDays(data.doctor.working_days);
    setShifts(parseRanges(data.doctor.working_hours).length ? parseRanges(data.doctor.working_hours) : [{ start: "", end: "" }]);
    setBreaks(parseRanges(data.doctor.breaks));
    setSlotDuration(String(data.doctor.slot_duration_minutes));
    setEffectiveFrom(data.doctor.effective_from || "");
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  function toggleDay(day: string) {
    setWorkingDays((prev) => (prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]));
    setSaved(false);
  }
  function setShift(i: number, range: TimeRange) {
    setShifts((prev) => prev.map((s, idx) => (idx === i ? range : s)));
    setSaved(false);
  }
  function addShift() {
    setShifts((prev) => [...prev, { start: "", end: "" }]);
  }
  function removeShift(i: number) {
    setShifts((prev) => prev.filter((_, idx) => idx !== i));
    setBreaks((prev) => prev.filter((_, idx) => idx !== i));
  }
  function setBreakRange(i: number, range: TimeRange) {
    setBreaks((prev) => {
      const next = [...prev];
      next[i] = range;
      return next;
    });
    setSaved(false);
  }

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setError(null);
    const result = await staffFetch("/api/doctor/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        working_days: workingDays,
        working_hours: serializeRanges(shifts),
        breaks: serializeRanges(breaks),
        slot_duration_minutes: Number(slotDuration) || 30,
        effective_from: effectiveFrom || null,
      }),
    });
    setSaving(false);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    setSaved(true);
    load();
  }

  async function handleAddLeave() {
    if (!leaveDate) return;
    setAddingLeave(true);
    const result = await staffFetch("/api/doctor/leave", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: leaveDate, reason: leaveReason || null }),
    });
    setAddingLeave(false);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    setLeaveDate("");
    setLeaveReason("");
    load();
  }

  async function handleDeleteLeave(leaveId: number) {
    await staffFetch(`/api/doctor/leave/${leaveId}/delete`, { method: "POST" });
    load();
  }

  return (
    <>
      <div className="mb-space-5">
        <h1 className="text-display">My schedule</h1>
        <p className="text-body">Working days, hours, and leave dates. Booking limits and capacity are set by your hospital's administrator.</p>
      </div>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      {!schedule ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : (
        <div className="space-y-space-4">
          <Card className="p-space-5">
            <p className="text-label mb-space-3 font-semibold text-ink-900">Working days</p>
            <div className="mb-space-4 flex flex-wrap items-center gap-space-2">
              {WEEKDAYS.map((day) => {
                const on = workingDays.includes(day);
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
            </div>

            <p className="text-label mb-space-2 font-semibold text-ink-900">Shifts &amp; breaks</p>
            <div className="mb-space-4 space-y-space-2">
              {shifts.map((shift, i) => (
                <div key={i} className="flex flex-wrap items-center gap-space-2 rounded-lg border border-line bg-paper p-space-3">
                  <span className="w-14 shrink-0 text-[12.5px] font-semibold text-ink-600">Shift {i + 1}</span>
                  <Input type="time" value={shift.start} onChange={(e) => setShift(i, { ...shift, start: e.target.value })} className="w-32" />
                  <span className="text-[12.5px] text-ink-400">to</span>
                  <Input type="time" value={shift.end} onChange={(e) => setShift(i, { ...shift, end: e.target.value })} className="w-32" />

                  <span className="ml-space-3 w-12 shrink-0 text-[12.5px] font-semibold text-ink-600">Break</span>
                  <Input
                    type="time"
                    value={breaks[i]?.start || ""}
                    onChange={(e) => setBreakRange(i, { start: e.target.value, end: breaks[i]?.end || "" })}
                    className="w-32"
                  />
                  <span className="text-[12.5px] text-ink-400">to</span>
                  <Input
                    type="time"
                    value={breaks[i]?.end || ""}
                    onChange={(e) => setBreakRange(i, { start: breaks[i]?.start || "", end: e.target.value })}
                    className="w-32"
                  />

                  {shifts.length > 1 && (
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

            <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
              <Field label="Slot duration" htmlFor="slot_duration" hint="minutes">
                <Input id="slot_duration" type="number" min={1} value={slotDuration} onChange={(e) => { setSlotDuration(e.target.value); setSaved(false); }} />
              </Field>
              <Field label="Effective from" htmlFor="effective_from" hint="optional — blank means immediately">
                <Input id="effective_from" type="date" value={effectiveFrom} onChange={(e) => { setEffectiveFrom(e.target.value); setSaved(false); }} />
              </Field>
            </div>

            <div className="flex items-center gap-space-3">
              <Button onClick={handleSave} disabled={saving}>
                {saving ? "Saving…" : "Save schedule"}
              </Button>
              {saved && <span className="text-[12.5px] font-semibold text-success">Saved</span>}
            </div>
          </Card>

          <Card className="p-space-5">
            <p className="text-label mb-space-3 font-semibold text-ink-900">Leave dates</p>
            {leave === null ? (
              <p className="text-hint mb-space-3">Loading…</p>
            ) : leave.length === 0 ? (
              <p className="text-hint mb-space-3">No leave dates set.</p>
            ) : (
              <ul className="mb-space-3 space-y-space-1">
                {leave.map((l) => (
                  <li key={l.id} className="flex items-center justify-between rounded-md bg-paper px-space-3 py-space-2 text-[12.5px]">
                    <span className="text-ink-900">
                      {l.date}
                      {l.reason ? ` — ${l.reason}` : ""}
                    </span>
                    <button type="button" onClick={() => handleDeleteLeave(l.id)} className="text-ink-400 hover:text-error">
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className="flex flex-wrap items-end gap-space-2">
              <div>
                <label className="mb-space-1 block text-[11px] font-semibold text-ink-400">Date</label>
                <Input type="date" value={leaveDate} onChange={(e) => setLeaveDate(e.target.value)} className="w-40" />
              </div>
              <Input placeholder="Reason (optional)" value={leaveReason} onChange={(e) => setLeaveReason(e.target.value)} className="max-w-[200px]" />
              <Button type="button" size="md" onClick={handleAddLeave} disabled={addingLeave || !leaveDate}>
                <Plus size={13} /> {addingLeave ? "Adding…" : "Add leave date"}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
