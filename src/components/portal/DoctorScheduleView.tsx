"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CalendarClock,
  CalendarOff,
  ChevronLeft,
  ChevronRight,
  Coffee,
  Plane,
  Plus,
  Settings2,
  Trash2,
  Video,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { AVATAR_TINTS, initials } from "@/app/portal/appointments/_components/appointments-columns";
import { TYPE_LABELS as APPT_TYPE_LABELS } from "@/hooks/useAppointments";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { AppointmentCalendar } from "@/components/doctor/AppointmentCalendar";
import { TodayScheduleTimeline } from "@/components/portal/TodayScheduleTimeline";
import { cn } from "@/lib/cn";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const SLOT_MIN = 30;

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

type Appointment = {
  id: number;
  phone: string;
  patient_display_id: string | null;
  department_name: string;
  scheduled_at: string;
  status: string;
  appointment_type_id: string | null;
  video_link: string | null;
};

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

function dateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function addDays(d: Date, n: number): Date {
  const next = new Date(d);
  next.setDate(d.getDate() + n);
  return next;
}
/** Monday of the calendar week containing `d` -- this app's own working_days
 * values (WEEKDAYS above) are Mon-first, so the grid stays Mon-first too. */
function mondayOf(d: Date): Date {
  const day = d.getDay(); // 0 (Sun) .. 6 (Sat)
  const monday = addDays(d, day === 0 ? -6 : 1 - day);
  monday.setHours(0, 0, 0, 0);
  return monday;
}
function minutesFromHHMM(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + (m || 0);
}
function formatHourLabel(mins: number): string {
  const h = Math.floor(mins / 60);
  const d = new Date(2000, 0, 1, h, mins % 60);
  return d.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: mins % 60 === 0 ? undefined : "2-digit",
  });
}
function formatRangeLabel(r: TimeRange): string {
  return `${formatHourLabel(minutesFromHHMM(r.start))} – ${formatHourLabel(minutesFromHHMM(r.end))}`;
}
function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

// Same three appointment_type_id values the rest of the portal recognizes
// (appointments-columns.tsx's own TYPE_ICONS) -- a color per type so the
// week grid's chip breakdown and the legend stay visually consistent.
const TYPE_DOT: Record<string, string> = {
  new: "bg-brand-600",
  followup: "bg-clay-700",
  tele: "bg-success",
};
function typeLabel(id: string | null): string {
  return (id && APPT_TYPE_LABELS[id]) || "Consultation";
}

/** A doctor's own self-service schedule -- a real weekly/monthly calendar of
 * configured working hours + breaks + leave, overlaid with that day's real
 * booked appointments (Week/Month/List, mirroring the reference mockup),
 * plus the pre-existing shift-editing form, now tucked behind its own
 * "Edit availability" dialog instead of an always-visible form -- the
 * mockup itself has no room for a full edit form on this page, but the
 * ability to actually change your working hours can't be dropped.
 * "Apply Leave" no longer opens a quick self-add dialog here -- leave now
 * ALWAYS goes through the Holiday Application page's real approval
 * workflow (an admin approves/rejects, and approval is what actually
 * blocks these dates below), so that button just links there; the `leave`
 * list here stays read-only (populated by that approval, same as before).
 * Self-fetches /api/doctor/schedule + /api/doctor/appointments/week; the
 * caller owns auth/guard/shell. */
export function DoctorScheduleView() {
  const router = useRouter();

  const [schedule, setSchedule] = useState<DoctorSchedule | null>(null);
  const [leave, setLeave] = useState<LeaveEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [view, setView] = useState<"week" | "month" | "list">("week");
  const [weekStartKey, setWeekStartKey] = useState(() => dateKey(mondayOf(new Date())));
  const [weekAppointments, setWeekAppointments] = useState<Appointment[] | null>(null);
  // Today's own appointments for the header stat tiles + "Today's schedule"
  // panel -- fetched independently of `weekStartKey` so navigating the grid
  // to a different week never changes what "today" means up top.
  const [todayAppointments, setTodayAppointments] = useState<Appointment[] | null>(null);

  const [editOpen, setEditOpen] = useState(false);

  const [workingDays, setWorkingDays] = useState<string[]>([]);
  const [shifts, setShifts] = useState<TimeRange[]>([{ start: "", end: "" }]);
  const [breaks, setBreaks] = useState<TimeRange[]>([]);
  const [slotDuration, setSlotDuration] = useState("30");
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const loadSchedule = useCallback(async () => {
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
    setShifts(
      parseRanges(data.doctor.working_hours).length
        ? parseRanges(data.doctor.working_hours)
        : [{ start: "", end: "" }],
    );
    setBreaks(parseRanges(data.doctor.breaks));
    setSlotDuration(String(data.doctor.slot_duration_minutes));
    setEffectiveFrom(data.doctor.effective_from || "");
  }, [router]);

  const loadWeek = useCallback(
    async (startKey: string) => {
      setWeekAppointments(null);
      const result = await staffFetch(`/api/doctor/appointments/week?start=${startKey}`);
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        else setError(result.error);
        return;
      }
      setWeekAppointments((result.data as { appointments: Appointment[] }).appointments);
    },
    [router],
  );

  const loadToday = useCallback(async () => {
    const result = await staffFetch("/api/doctor/appointments/week");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      return;
    }
    const todayKey = dateKey(new Date());
    const all = (result.data as { appointments: Appointment[] }).appointments;
    setTodayAppointments(all.filter((a) => dateKey(new Date(a.scheduled_at)) === todayKey));
  }, [router]);

  useEffect(() => {
    loadSchedule();
  }, [loadSchedule]);
  useEffect(() => {
    loadToday();
  }, [loadToday]);
  useEffect(() => {
    loadWeek(weekStartKey);
  }, [weekStartKey, loadWeek]);

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
      if (!result.unauthorized) toast.error("Couldn't save schedule", result.error);
      return;
    }
    setSaved(true);
    toast.success("Schedule saved");
    loadSchedule();
  }

  const weekStart = useMemo(() => new Date(`${weekStartKey}T00:00:00`), [weekStartKey]);
  const weekDates = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)),
    [weekStart],
  );
  const weekLabel = useMemo(() => {
    const end = weekDates[6];
    const sameMonth =
      weekStart.getMonth() === end.getMonth() && weekStart.getFullYear() === end.getFullYear();
    const startLabel = weekStart.toLocaleDateString(undefined, {
      day: "numeric",
      month: sameMonth ? undefined : "short",
    });
    const endLabel = end.toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
    return `${startLabel} – ${endLabel}`;
  }, [weekStart, weekDates]);

  function goToWeek(delta: number) {
    setWeekStartKey(dateKey(addDays(weekStart, delta * 7)));
  }
  function goToToday() {
    setWeekStartKey(dateKey(mondayOf(new Date())));
  }

  const apptsByDate = useMemo(() => {
    const map = new Map<string, Appointment[]>();
    for (const a of weekAppointments || []) {
      const key = dateKey(new Date(a.scheduled_at));
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(a);
    }
    return map;
  }, [weekAppointments]);

  const leaveByDate = useMemo(() => {
    const map = new Map<string, LeaveEntry>();
    for (const l of leave || []) map.set(l.date, l);
    return map;
  }, [leave]);

  const shiftRanges = useMemo(
    () => parseRanges(schedule?.working_hours || []).filter((r) => r.start && r.end),
    [schedule],
  );
  const breakRanges = useMemo(
    () => parseRanges(schedule?.breaks || []).filter((r) => r.start && r.end),
    [schedule],
  );
  const workingDaySet = useMemo(() => new Set(schedule?.working_days || []), [schedule]);

  const { startMin, endMin } = useMemo(() => {
    let lo = 8 * 60,
      hi = 18 * 60;
    for (const r of [...shiftRanges, ...breakRanges]) {
      lo = Math.min(lo, minutesFromHHMM(r.start));
      hi = Math.max(hi, minutesFromHHMM(r.end));
    }
    for (const a of weekAppointments || []) {
      const d = new Date(a.scheduled_at);
      const mins = d.getHours() * 60 + d.getMinutes();
      lo = Math.min(lo, mins);
      hi = Math.max(hi, mins + 60);
    }
    return { startMin: Math.floor(lo / 60) * 60, endMin: Math.ceil(hi / 60) * 60 };
  }, [shiftRanges, breakRanges, weekAppointments]);

  const totalRows = Math.max(1, Math.round((endMin - startMin) / SLOT_MIN));
  function rowFor(mins: number): number {
    return Math.round((mins - startMin) / SLOT_MIN) + 1;
  }

  const todayKey = dateKey(new Date());
  const teleconsultationsToday = (todayAppointments || []).filter(
    (a) => a.appointment_type_id === "tele",
  ).length;
  const todayIsWorking = workingDaySet.has(WEEKDAYS[(new Date().getDay() + 6) % 7]);
  const todayOnLeave = leaveByDate.has(todayKey);
  const todayShiftLabel = todayOnLeave
    ? "On leave"
    : !todayIsWorking
      ? "Off today"
      : shiftRanges.length
        ? shiftRanges.map(formatRangeLabel).join(", ")
        : "No hours set";
  const now = new Date();
  const nowMins = now.getHours() * 60 + now.getMinutes();
  const onDutyNow =
    todayIsWorking &&
    !todayOnLeave &&
    shiftRanges.some(
      (r) => nowMins >= minutesFromHHMM(r.start) && nowMins <= minutesFromHHMM(r.end),
    );

  const upcomingLeave = (leave || [])
    .filter((l) => l.date >= todayKey)
    .sort((a, b) => a.date.localeCompare(b.date));
  const upcomingLeaveHint =
    upcomingLeave.length === 0
      ? "No upcoming leave"
      : upcomingLeave.length === 1
        ? new Date(`${upcomingLeave[0].date}T00:00:00`).toLocaleDateString(undefined, {
            day: "numeric",
            month: "short",
          })
        : `${new Date(`${upcomingLeave[0].date}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" })} – ${new Date(`${upcomingLeave[upcomingLeave.length - 1].date}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}`;

  return (
    <>
      <div className="mb-space-5 gap-space-3 flex flex-wrap items-center justify-between">
        <div>
          <h1 className="text-display">Schedule</h1>
          <p className="text-body">Plan your availability and manage your appointments.</p>
        </div>
        <div className="gap-space-2 flex items-center">
          <button
            type="button"
            onClick={() => setEditOpen(true)}
            title="Edit working days, hours &amp; breaks"
            className="border-line text-ink-600 flex h-9 w-9 items-center justify-center rounded-md border hover:bg-black/[0.04]"
          >
            <Settings2 size={16} />
          </button>
          <Button variant="secondary" size="md" href="/portal/holiday-application">
            <Plane size={15} /> Apply Leave
          </Button>
          <Button
            size="md"
            disabled
            title="Booking a single ad-hoc slot isn't built yet -- edit your working hours instead."
          >
            <Plus size={15} /> Add Slot
          </Button>
        </div>
      </div>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      {!schedule ? (
        <p className="text-ink-400 text-[13px]">Loading…</p>
      ) : (
        <>
          <div className="mb-space-5 gap-space-4 xs:grid-cols-2 grid grid-cols-1 lg:grid-cols-4">
            <InfoTile
              icon={CalendarClock}
              tint="brand"
              label="Today's shift"
              value={todayShiftLabel}
              hint={
                todayIsWorking && !todayOnLeave ? (onDutyNow ? "On duty" : "Off duty") : undefined
              }
            />
            <InfoTile
              icon={CalendarClock}
              tint="success"
              label="OPD hours"
              value={todayShiftLabel}
              hint="Today's working hours"
            />
            <InfoTile
              icon={Video}
              tint="brand"
              label="Teleconsultation slots"
              value={String(teleconsultationsToday)}
              hint={`${teleconsultationsToday} scheduled today`}
            />
            <InfoTile
              icon={Plane}
              tint="clay"
              label="Upcoming leave"
              value={String(upcomingLeave.length)}
              hint={
                upcomingLeave.length
                  ? `${upcomingLeave.length} day${upcomingLeave.length === 1 ? "" : "s"} · ${upcomingLeaveHint}`
                  : upcomingLeaveHint
              }
            />
          </div>

          <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-3">
            <Card className="p-space-4 lg:col-span-2">
              <div className="mb-space-4 gap-space-2 flex flex-wrap items-center justify-between">
                <div className="gap-space-2 flex items-center">
                  <h3 className="text-label text-ink-900 font-bold">My Schedule</h3>
                  {view === "week" && (
                    <div className="gap-space-1 flex items-center">
                      <button
                        type="button"
                        onClick={() => goToWeek(-1)}
                        className="text-ink-600 flex h-7 w-7 items-center justify-center rounded-md hover:bg-black/[0.04]"
                      >
                        <ChevronLeft size={15} />
                      </button>
                      <span className="text-ink-600 text-[12.5px] font-semibold">{weekLabel}</span>
                      <button
                        type="button"
                        onClick={() => goToWeek(1)}
                        className="text-ink-600 flex h-7 w-7 items-center justify-center rounded-md hover:bg-black/[0.04]"
                      >
                        <ChevronRight size={15} />
                      </button>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={goToToday}
                    className="border-line px-space-2 text-ink-600 rounded-md border py-1 text-[11.5px] font-semibold hover:bg-black/[0.04]"
                  >
                    Today
                  </button>
                </div>
                <div className="border-line flex rounded-md border p-0.5">
                  {(["week", "month", "list"] as const).map((v) => (
                    <button
                      key={v}
                      type="button"
                      onClick={() => setView(v)}
                      className={cn(
                        "px-space-3 rounded py-1 text-[12px] font-semibold capitalize transition-colors duration-150",
                        view === v
                          ? "bg-brand-600 text-white"
                          : "text-ink-600 hover:bg-black/[0.04]",
                      )}
                    >
                      {v}
                    </button>
                  ))}
                </div>
              </div>

              {view === "month" && <AppointmentCalendar />}
              {view === "week" && (
                <WeekGrid
                  weekDates={weekDates}
                  workingDaySet={workingDaySet}
                  leaveByDate={leaveByDate}
                  apptsByDate={apptsByDate}
                  shiftRanges={shiftRanges}
                  breakRanges={breakRanges}
                  startMin={startMin}
                  totalRows={totalRows}
                  rowFor={rowFor}
                />
              )}
              {view === "list" && (
                <WeekList
                  weekDates={weekDates}
                  apptsByDate={apptsByDate}
                  leaveByDate={leaveByDate}
                />
              )}
            </Card>

            <div className="space-y-space-4">
              <Card className="p-space-4">
                <h3 className="text-label mb-space-3 text-ink-900 font-bold">
                  Today&apos;s schedule
                </h3>
                <TodayScheduleTimeline appointments={todayAppointments || []} />
              </Card>

              <Card className="p-space-4">
                <div className="mb-space-3 gap-space-2 flex items-center">
                  <h3 className="text-label text-ink-900 font-bold">Today&apos;s tasks</h3>
                  <span className="px-space-2 text-ink-400 rounded-full bg-black/[0.04] py-0.5 text-[10px] font-bold">
                    Coming soon
                  </span>
                </div>
                <p className="mb-space-2 text-ink-400 text-[12px]">
                  Task tracking isn&apos;t built yet -- preview of the upcoming layout.
                </p>
                <ul className="space-y-space-2 opacity-50">
                  {[
                    "Complete OPD notes",
                    "Review lab reports",
                    "Respond to patient messages",
                    "Plan tomorrow's slots",
                  ].map((t) => (
                    <li
                      key={t}
                      className="gap-space-2 text-ink-600 flex items-center text-[12.5px]"
                    >
                      <span className="border-line h-4 w-4 shrink-0 rounded-full border-2" /> {t}
                    </li>
                  ))}
                </ul>
              </Card>

              <Card className="p-space-4">
                <h3 className="text-label mb-space-3 text-ink-900 font-bold">Schedule legend</h3>
                <div className="gap-space-2 text-ink-600 grid grid-cols-2 text-[12px]">
                  <LegendItem dot="bg-brand-100 border border-brand-300" label="Working hours" />
                  <LegendItem dot="bg-black/[0.06] border border-line" label="Break" />
                  <LegendItem dot="bg-clay-100 border border-clay-300" label="Leave" />
                  <LegendItem dot={TYPE_DOT.new} label="OPD / new" round />
                  <LegendItem dot={TYPE_DOT.followup} label="Follow-up" round />
                  <LegendItem dot={TYPE_DOT.tele} label="Teleconsultation" round />
                </div>
              </Card>
            </div>
          </div>
        </>
      )}

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-2xl">
          <DialogTitle>Edit availability</DialogTitle>
          <p className="text-hint mb-space-4">
            Working days, hours, and breaks. Booking limits and capacity are set by your
            hospital&apos;s administrator.
          </p>
          <div>
            <p className="text-label mb-space-3 text-ink-900 font-semibold">Working days</p>
            <div className="mb-space-4 gap-space-2 flex flex-wrap items-center">
              {WEEKDAYS.map((day) => {
                const on = workingDays.includes(day);
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
            </div>

            <p className="text-label mb-space-2 text-ink-900 font-semibold">Shifts &amp; breaks</p>
            <div className="mb-space-4 space-y-space-2">
              {shifts.map((shift, i) => (
                <div
                  key={i}
                  className="gap-space-2 border-line bg-paper p-space-3 flex flex-wrap items-center rounded-lg border"
                >
                  <span className="text-ink-600 w-14 shrink-0 text-[12.5px] font-semibold">
                    Shift {i + 1}
                  </span>
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

                  <span className="ml-space-3 text-ink-600 w-12 shrink-0 text-[12.5px] font-semibold">
                    Break
                  </span>
                  <Input
                    type="time"
                    value={breaks[i]?.start || ""}
                    onChange={(e) =>
                      setBreakRange(i, { start: e.target.value, end: breaks[i]?.end || "" })
                    }
                    className="w-32"
                  />
                  <span className="text-ink-400 text-[12.5px]">to</span>
                  <Input
                    type="time"
                    value={breaks[i]?.end || ""}
                    onChange={(e) =>
                      setBreakRange(i, { start: breaks[i]?.start || "", end: e.target.value })
                    }
                    className="w-32"
                  />

                  {shifts.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeShift(i)}
                      className="text-ink-400 hover:text-error ml-auto shrink-0"
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
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

            <div className="gap-x-space-4 grid grid-cols-1 sm:grid-cols-2">
              <Field label="Slot duration" htmlFor="slot_duration" hint="minutes">
                <Input
                  id="slot_duration"
                  type="number"
                  min={1}
                  value={slotDuration}
                  onChange={(e) => {
                    setSlotDuration(e.target.value);
                    setSaved(false);
                  }}
                />
              </Field>
              <Field
                label="Effective from"
                htmlFor="effective_from"
                hint="optional — blank means immediately"
              >
                <Input
                  id="effective_from"
                  type="date"
                  value={effectiveFrom}
                  onChange={(e) => {
                    setEffectiveFrom(e.target.value);
                    setSaved(false);
                  }}
                />
              </Field>
            </div>

            <div className="gap-space-3 flex items-center">
              <Button onClick={handleSave} disabled={saving}>
                {saving ? "Saving…" : "Save schedule"}
              </Button>
              {saved && <span className="text-success text-[12.5px] font-semibold">Saved</span>}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function InfoTile({
  icon: Icon,
  tint,
  label,
  value,
  hint,
}: {
  icon: typeof CalendarClock;
  tint: "brand" | "success" | "clay";
  label: string;
  value: string;
  hint?: string;
}) {
  const tintClasses =
    tint === "success"
      ? "bg-success-tint text-success"
      : tint === "clay"
        ? "bg-clay-100 text-clay-700"
        : "bg-brand-50 text-brand-600";
  return (
    <Card className="p-space-4">
      <div className="gap-space-3 flex items-center">
        <span
          className={cn(
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-full",
            tintClasses,
          )}
        >
          <Icon size={20} strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <p className="text-hint truncate">{label}</p>
          <p className="text-ink-900 truncate text-[16px] font-bold">{value}</p>
          {hint && <p className="text-ink-500 truncate text-[11px]">{hint}</p>}
        </div>
      </div>
    </Card>
  );
}

function LegendItem({ dot, label, round }: { dot: string; label: string; round?: boolean }) {
  return (
    <span className="gap-space-2 flex items-center">
      <span className={cn("h-3 w-3 shrink-0", round ? "rounded-full" : "rounded-sm", dot)} />
      {label}
    </span>
  );
}

function AppointmentTypeChips({ appointments }: { appointments: Appointment[] }) {
  const counts = new Map<string, number>();
  for (const a of appointments) {
    const key = a.appointment_type_id || "new";
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  if (counts.size === 0) return null;
  return (
    <div className="gap-x-space-2 mt-1 flex flex-wrap gap-y-0.5">
      {[...counts.entries()].map(([type, count]) => (
        <span
          key={type}
          className="text-ink-700 inline-flex items-center gap-1 text-[10.5px] font-semibold"
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", TYPE_DOT[type] || "bg-ink-400")} />
          {typeLabel(type)} {count}
        </span>
      ))}
    </div>
  );
}

function WeekGrid({
  weekDates,
  workingDaySet,
  leaveByDate,
  apptsByDate,
  shiftRanges,
  breakRanges,
  startMin,
  totalRows,
  rowFor,
}: {
  weekDates: Date[];
  workingDaySet: Set<string>;
  leaveByDate: Map<string, LeaveEntry>;
  apptsByDate: Map<string, Appointment[]>;
  shiftRanges: TimeRange[];
  breakRanges: TimeRange[];
  startMin: number;
  totalRows: number;
  rowFor: (mins: number) => number;
}) {
  const todayKey = dateKey(new Date());
  const hourMarks: number[] = [];
  for (let m = startMin; m < startMin + totalRows * SLOT_MIN; m += 60) hourMarks.push(m);

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[720px]">
        <div className="border-line pb-space-2 grid grid-cols-[56px_repeat(7,1fr)] gap-x-1 border-b text-center">
          <div />
          {weekDates.map((d) => {
            const key = dateKey(d);
            const isToday = key === todayKey;
            return (
              <div
                key={key}
                className={cn("rounded-md py-1 text-[12px]", isToday && "bg-brand-50")}
              >
                <p className="text-ink-900 font-semibold">{WEEKDAYS[(d.getDay() + 6) % 7]}</p>
                <p className="text-ink-500">
                  {d.toLocaleDateString(undefined, { day: "numeric", month: "short" })}
                </p>
              </div>
            );
          })}
        </div>

        <div
          className="mt-space-2 relative grid grid-cols-[56px_repeat(7,1fr)] gap-x-1"
          style={{ gridTemplateRows: `repeat(${totalRows}, 1.75rem)` }}
        >
          {hourMarks.map((m) => (
            <div
              key={m}
              style={{ gridColumn: 1, gridRow: `${rowFor(m)} / span 2` }}
              className="pr-space-2 text-ink-400 text-right text-[10.5px]"
            >
              {formatHourLabel(m)}
            </div>
          ))}

          {weekDates.map((d, colIdx) => {
            const key = dateKey(d);
            const isWorking = workingDaySet.has(WEEKDAYS[colIdx]);
            const onLeave = leaveByDate.get(key);
            const dayAppts = apptsByDate.get(key) || [];
            const col = colIdx + 2;

            if (onLeave) {
              return (
                <div
                  key={key}
                  style={{ gridColumn: col, gridRow: `1 / ${totalRows + 1}` }}
                  className="border-clay-300 bg-clay-100 p-space-2 flex flex-col items-center justify-center gap-1 rounded-md border text-center"
                >
                  <Plane size={16} className="text-clay-700" />
                  <span className="text-clay-700 text-[11px] font-semibold">On leave</span>
                  {onLeave.reason && (
                    <span className="text-clay-700/80 text-[10px]">{onLeave.reason}</span>
                  )}
                </div>
              );
            }

            if (!isWorking) {
              if (dayAppts.length === 0) {
                return (
                  <div
                    key={key}
                    style={{ gridColumn: col, gridRow: `1 / ${totalRows + 1}` }}
                    className="border-line flex flex-col items-center justify-center gap-1 rounded-md border border-dashed text-center"
                  >
                    <CalendarOff size={16} className="text-ink-300" />
                    <span className="text-ink-400 text-[11px]">No slots scheduled</span>
                  </div>
                );
              }
              const times = dayAppts.map((a) => new Date(a.scheduled_at));
              const lo = Math.min(...times.map((t) => t.getHours() * 60 + t.getMinutes()));
              const hi = Math.max(...times.map((t) => t.getHours() * 60 + t.getMinutes())) + 60;
              return (
                <div
                  key={key}
                  style={{ gridColumn: col, gridRow: `${rowFor(lo)} / ${rowFor(hi)}` }}
                  className="border-clay-300 bg-clay-100 p-space-2 rounded-md border"
                >
                  <p className="text-clay-700 text-[11px] font-semibold">Booked (day off)</p>
                  <AppointmentTypeChips appointments={dayAppts} />
                </div>
              );
            }

            return (
              <div
                key={key}
                style={{ gridColumn: col, gridRow: `1 / ${totalRows + 1}` }}
                className="relative"
              >
                {shiftRanges.map((r, i) => (
                  <div
                    key={`shift-${i}`}
                    style={{
                      gridRow: `${rowFor(minutesFromHHMM(r.start))} / ${rowFor(minutesFromHHMM(r.end))}`,
                    }}
                    className="border-brand-300 bg-brand-50 p-space-2 absolute inset-x-0 rounded-md border"
                  >
                    <p className="text-brand-700 text-[11px] font-semibold">
                      {formatRangeLabel(r)}
                    </p>
                    <AppointmentTypeChips appointments={dayAppts} />
                  </div>
                ))}
                {breakRanges.map((r, i) => (
                  <div
                    key={`break-${i}`}
                    style={{
                      gridRow: `${rowFor(minutesFromHHMM(r.start))} / ${rowFor(minutesFromHHMM(r.end))}`,
                      zIndex: 2,
                    }}
                    className="border-line bg-paper/95 px-space-2 text-ink-500 absolute inset-x-1 flex items-center gap-1 rounded-md border text-[10.5px] font-semibold"
                  >
                    <Coffee size={11} /> Break
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function WeekList({
  weekDates,
  apptsByDate,
  leaveByDate,
}: {
  weekDates: Date[];
  apptsByDate: Map<string, Appointment[]>;
  leaveByDate: Map<string, LeaveEntry>;
}) {
  const rows = weekDates
    .flatMap((d) => {
      const key = dateKey(d);
      return (apptsByDate.get(key) || []).map((a) => ({ day: d, appt: a }));
    })
    .sort(
      (a, b) => new Date(a.appt.scheduled_at).getTime() - new Date(b.appt.scheduled_at).getTime(),
    );

  const leaveDays = weekDates.filter((d) => leaveByDate.has(dateKey(d)));

  if (rows.length === 0 && leaveDays.length === 0) {
    return (
      <p className="py-space-6 text-ink-400 text-center text-[13px]">No appointments this week.</p>
    );
  }

  return (
    <div className="space-y-space-2">
      {leaveDays.map((d) => (
        <div
          key={dateKey(d)}
          className="gap-space-2 bg-clay-100 px-space-3 py-space-2 text-clay-700 flex items-center rounded-md text-[12.5px]"
        >
          <Plane size={14} /> On leave —{" "}
          {d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" })}
        </div>
      ))}
      {rows.map(({ day, appt }) => (
        <div
          key={appt.id}
          className="gap-space-3 border-line p-space-3 flex items-center rounded-md border"
        >
          <div className="text-ink-500 w-24 shrink-0 text-[12px]">
            {day.toLocaleDateString(undefined, {
              weekday: "short",
              day: "numeric",
              month: "short",
            })}
          </div>
          <span
            className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-bold",
              AVATAR_TINTS[appt.id % AVATAR_TINTS.length],
            )}
          >
            {initials(appt.patient_display_id, appt.phone)}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-ink-900 truncate text-[13.5px] font-semibold">
              {appt.patient_display_id || appt.phone}
            </p>
            <p className="text-ink-600 truncate text-[12px]">
              {typeLabel(appt.appointment_type_id)} · {appt.department_name}
            </p>
          </div>
          <span className="text-ink-900 shrink-0 text-[12.5px] font-semibold tabular-nums">
            {formatTime(appt.scheduled_at)}
          </span>
        </div>
      ))}
    </div>
  );
}
