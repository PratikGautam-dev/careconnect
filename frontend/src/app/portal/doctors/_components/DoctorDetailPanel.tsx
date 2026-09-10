"use client";

import {
  Building2,
  CalendarClock,
  CalendarPlus,
  Eye,
  IdCard,
  Mail,
  MapPin,
  MessageCircle,
  Pencil,
  Phone,
  Power,
  UserRound,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import type { Doctor } from "@/hooks/useDoctors";
import { AVATAR_TINTS } from "./doctors-columns";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
}

function formatClockTime(hhmm: string): string {
  const [hStr, mStr = "00"] = hhmm.split(":");
  const h = Number(hStr);
  if (Number.isNaN(h)) return hhmm;
  const period = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 || 12;
  return `${h12}:${mStr} ${period}`;
}

/** "Mon - Sat" for a contiguous run starting Monday, else a comma list --
 * working_days is a fixed-order subset of Mon..Sun (doctors.py's
 * _WEEKDAY_ABBREVS), not necessarily contiguous or Monday-starting. */
function formatWorkingDays(days: string[]): string {
  const order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const sorted = [...days].sort((a, b) => order.indexOf(a) - order.indexOf(b));
  const isContiguousFromMon = sorted.every((d, i) => d === order[i]);
  return isContiguousFromMon && sorted.length > 1 ? `${sorted[0]} - ${sorted[sorted.length - 1]}` : sorted.join(", ");
}

function DetailRow({ icon: Icon, label, value }: { icon: typeof UserRound; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-space-3 text-[13px]">
      <span className="flex items-center gap-space-2 text-ink-400">
        <Icon size={14} className="shrink-0" /> {label}
      </span>
      <span className="truncate text-right font-medium text-ink-900">{value}</span>
    </div>
  );
}

type Props = {
  doctor: Doctor | null;
  index: number;
  canManage: boolean;
  onEdit: (doc: Doctor) => void;
  togglingId: string | null;
  onToggleActive: (doc: Doctor) => void;
  scheduleOpen: boolean;
  onToggleSchedule: () => void;
  leaveOpen: boolean;
  onToggleLeave: () => void;
  onBookAppointment: () => void;
};

/** Right-rail "selected doctor" profile card -- only ever shows fields this
 * schema actually has (qualification/specialization/department/experience/
 * email/working hours, all real); Employee ID, phone, room/cabin, and a
 * live "available since HH:MM" aren't tracked anywhere here, so they're
 * shown as "—" with a note rather than invented. */
export function DoctorDetailPanel({
  doctor, index, canManage, onEdit, togglingId, onToggleActive, scheduleOpen, onToggleSchedule, leaveOpen, onToggleLeave,
  onBookAppointment,
}: Props) {
  if (!doctor) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-center text-[13px] text-ink-400">Select a doctor to view their profile.</p>
      </Card>
    );
  }

  const hours = doctor.working_hours.length > 0 ? doctor.working_hours.map((r) => {
    const [start, end] = r.split("-");
    return start && end ? `${formatClockTime(start)} - ${formatClockTime(end)}` : r;
  }).join(", ") : null;

  return (
    <Card className="p-space-4">
      <div className="mb-space-4 flex flex-col items-center text-center">
        <span
          className={cn(
            "mb-space-2 flex h-16 w-16 items-center justify-center rounded-full text-[20px] font-bold",
            AVATAR_TINTS[index % AVATAR_TINTS.length],
          )}
        >
          {initials(doctor.name)}
        </span>
        <span
          className={cn(
            "mb-space-1 rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
            doctor.is_active ? "bg-success-tint text-success" : "bg-black/4 text-ink-600",
          )}
        >
          {doctor.is_active ? "Available" : "Unavailable"}
        </span>
        <p className="text-[15px] font-bold text-ink-900">Dr. {doctor.name}</p>
        {doctor.qualification && <p className="text-[12.5px] text-ink-600">{doctor.qualification}</p>}
        {doctor.specialization && <p className="text-[12px] text-ink-400">{doctor.specialization}</p>}
      </div>

      <div className="space-y-space-2 border-t border-line pt-space-3">
        <DetailRow icon={Building2} label="Department" value={doctor.department_name} />
        <DetailRow icon={IdCard} label="Employee ID" value="—" />
        <DetailRow icon={CalendarClock} label="Experience" value={doctor.years_experience != null ? `${doctor.years_experience} years` : "—"} />
        <DetailRow icon={Phone} label="Phone" value="—" />
        <DetailRow icon={Mail} label="Email" value={doctor.email || "—"} />
        <DetailRow icon={MapPin} label="Location" value="—" />
      </div>

      <div className="mt-space-3 rounded-md border border-line bg-paper p-space-3">
        <p className="mb-space-1 flex items-center gap-space-2 text-[12px] font-semibold text-ink-600">
          <CalendarClock size={13} /> Consulting hours
        </p>
        <p className="text-[13px] text-ink-900">
          {doctor.working_days.length > 0 ? formatWorkingDays(doctor.working_days) : "—"}
          {hours ? ` · ${hours}` : ""}
        </p>
      </div>

      <p className="text-hint mt-space-2">
        Employee ID, phone, location, and room/cabin aren&apos;t tracked in this app yet — availability shown above is
        the real Available/Unavailable toggle, not a live &quot;since HH:MM&quot; check-in.
      </p>

      <div className="mt-space-4 border-t border-line pt-space-3">
        <p className="text-label mb-space-2 font-bold text-ink-900">Quick actions</p>
        <div className="grid grid-cols-2 gap-space-2">
          {canManage && (
            <button
              type="button"
              onClick={() => onEdit(doctor)}
              className="flex items-center gap-space-2 rounded-md border border-line px-space-3 py-space-2 text-[12.5px] font-semibold text-ink-900 hover:border-brand-300 hover:bg-brand-50"
            >
              <Pencil size={14} /> Edit profile
            </button>
          )}
          <button
            type="button"
            onClick={onBookAppointment}
            className="flex items-center gap-space-2 rounded-md border border-line px-space-3 py-space-2 text-[12.5px] font-semibold text-ink-900 hover:border-brand-300 hover:bg-brand-50"
          >
            <CalendarPlus size={14} /> Book appointment
          </button>
          <button
            type="button"
            onClick={onToggleSchedule}
            className={cn(
              "flex items-center gap-space-2 rounded-md border px-space-3 py-space-2 text-[12.5px] font-semibold",
              scheduleOpen ? "border-brand-600 bg-brand-50 text-brand-700" : "border-line text-ink-900 hover:border-brand-300 hover:bg-brand-50",
            )}
          >
            <Eye size={14} /> View schedule
          </button>
          {canManage && (
            <button
              type="button"
              onClick={() => onToggleActive(doctor)}
              disabled={togglingId === doctor.id}
              className="flex items-center gap-space-2 rounded-md border border-line px-space-3 py-space-2 text-[12.5px] font-semibold text-ink-900 hover:border-brand-300 hover:bg-brand-50 disabled:opacity-50"
            >
              <Power size={14} /> {doctor.is_active ? "Mark unavailable" : "Mark available"}
            </button>
          )}
          <button
            type="button"
            disabled
            title="Coming soon — no doctor-facing internal messaging exists yet"
            className="flex cursor-not-allowed items-center gap-space-2 rounded-md border border-line px-space-3 py-space-2 text-[12.5px] font-semibold text-ink-400"
          >
            <MessageCircle size={14} /> Send message
          </button>
          {canManage && (
            <button
              type="button"
              onClick={onToggleLeave}
              className={cn(
                "col-span-2 flex items-center gap-space-2 rounded-md border px-space-3 py-space-2 text-[12.5px] font-semibold",
                leaveOpen ? "border-brand-600 bg-brand-50 text-brand-700" : "border-line text-ink-900 hover:border-brand-300 hover:bg-brand-50",
              )}
            >
              <CalendarClock size={14} /> Manage leave
            </button>
          )}
        </div>
      </div>
    </Card>
  );
}
