"use client";

import {
  Building2,
  CalendarClock,
  CalendarPlus,
  Eye,
  IdCard,
  KeyRound,
  Mail,
  MapPin,
  MessageCircle,
  Pencil,
  Phone,
  Power,
  UserRound,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { QuickActionList, type QuickAction } from "@/components/portal/QuickActions";
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
  onCreateLogin: (doc: Doctor) => void;
};

/** Right-rail "selected doctor" profile card -- every field shown is real,
 * including Leave balance (leave_requests + hospitals.doctor_annual_leave_days,
 * migration 20260912065049 -- null for a doctor with no login yet, since
 * there's no identity to attach a leave request to). Applying for leave
 * FROM this panel is still a later page (confirmed with the user) -- only
 * the balance display itself is in scope here. A live "available since
 * HH:MM" check-in doesn't exist either; availability is the real Available/
 * Unavailable toggle only. The Email row and "Create login" quick action
 * are this doctor's unified-login status (login_email/login_staff_id, an
 * outer join to staff_details/identities) -- not a profile contact field,
 * the same login a doctor uses to sign into the shared portal (see the
 * Staff page's own role="doctor" rows). */
export function DoctorDetailPanel({
  doctor, index, canManage, onEdit, togglingId, onToggleActive, scheduleOpen, onToggleSchedule, leaveOpen, onToggleLeave,
  onBookAppointment, onCreateLogin,
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

  const quickActions: QuickAction[] = [
    ...(canManage ? [{ label: "Edit profile", icon: Pencil, onClick: () => onEdit(doctor) }] : []),
    { label: "Book appointment", icon: CalendarPlus, onClick: onBookAppointment },
    { label: "View schedule", icon: Eye, onClick: onToggleSchedule, active: scheduleOpen },
    ...(canManage
      ? [{
          label: doctor.is_active ? "Mark unavailable" : "Mark available",
          icon: Power,
          onClick: () => onToggleActive(doctor),
          disabled: togglingId === doctor.id,
        }]
      : []),
    { label: "Send message", icon: MessageCircle, disabled: true, title: "Coming soon — no doctor-facing internal messaging exists yet" },
    ...(canManage && !doctor.login_staff_id
      ? [{ label: "Create login", icon: KeyRound, onClick: () => onCreateLogin(doctor), fullWidth: true }]
      : []),
    ...(canManage
      ? [{ label: "Manage leave", icon: CalendarClock, onClick: onToggleLeave, active: leaveOpen, fullWidth: true }]
      : []),
  ];

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
        <DetailRow icon={IdCard} label="Employee ID" value={doctor.employee_id || "—"} />
        <DetailRow icon={CalendarClock} label="Experience" value={doctor.years_experience != null ? `${doctor.years_experience} years` : "—"} />
        <DetailRow icon={Phone} label="Phone" value={doctor.phone || "—"} />
        <DetailRow icon={Mail} label="Login email" value={doctor.login_email || "No login yet"} />
        <DetailRow icon={MapPin} label="Location" value={doctor.location || "—"} />
        <DetailRow
          icon={CalendarClock}
          label="Leave balance"
          value={
            doctor.leave_balance_total != null
              ? `${doctor.leave_balance_total - (doctor.leave_balance_used ?? 0)} / ${doctor.leave_balance_total} days`
              : "—"
          }
        />
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
        Leave balance is real (Leave Requests page, Settings &gt; Leave policy) — applying for leave from here is still
        a later page. Availability is the real Available/Unavailable toggle, not a live &quot;since HH:MM&quot; check-in.
      </p>

      <div className="mt-space-4 border-t border-line pt-space-3">
        <p className="text-label mb-space-2 font-bold text-ink-900">Quick actions</p>
        <QuickActionList actions={quickActions} columns={2} size="sm" />
      </div>
    </Card>
  );
}
