"use client";

import {
  Building2,
  CalendarCheck,
  CalendarClock,
  CalendarDays,
  Clock,
  History,
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
import { formatWorkingDays, formatWorkingHours } from "@/lib/formatSchedule";
import type { Doctor } from "@/hooks/useDoctors";
import { AVATAR_TINTS } from "./doctors-columns";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
}

function DetailRow({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof UserRound;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="gap-space-3 flex items-center justify-between text-[13px]">
      <span className="gap-space-2 text-ink-400 flex items-center">
        <Icon size={14} className="shrink-0" /> {label}
      </span>
      <span className="text-ink-900 truncate text-right font-medium">{value}</span>
    </div>
  );
}

type Props = {
  doctor: Doctor | null;
  index: number;
  canManage: boolean;
  canViewAttendance: boolean;
  canViewLeaveHistory: boolean;
  canManageLeave: boolean;
  onEdit: (doc: Doctor) => void;
  togglingId: string | null;
  onToggleActive: (doc: Doctor) => void;
  onRunningLate: (doc: Doctor) => void;
  onCreateLogin: (doc: Doctor) => void;
  onResetPassword: (doc: Doctor) => void;
  onManageLeave: (doc: Doctor) => void;
  onViewAttendanceHistory: (doc: Doctor) => void;
  onViewLeaveHistory: (doc: Doctor) => void;
};

/** Right-rail "selected doctor" profile card -- every field shown is real.
 * Leave balance is null for a doctor with no login yet, since there's no
 * identity to attach a leave request to; applying for leave happens on a
 * separate page. Availability is the real Available/Unavailable toggle
 * only, no live "available since HH:MM" check-in. The Email row and
 * "Create login" quick action reflect this doctor's unified-login status
 * (login_email/login_staff_id) -- the same login used to sign into the
 * shared portal, not a profile contact field. */
export function DoctorDetailPanel({
  doctor,
  index,
  canManage,
  canViewAttendance,
  canViewLeaveHistory,
  canManageLeave,
  onEdit,
  togglingId,
  onToggleActive,
  onRunningLate,
  onCreateLogin,
  onResetPassword,
  onManageLeave,
  onViewAttendanceHistory,
  onViewLeaveHistory,
}: Props) {
  if (!doctor) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-ink-400 text-center text-[13px]">
          Select a doctor to view their profile.
        </p>
      </Card>
    );
  }

  const hours = formatWorkingHours(doctor.working_hours);

  const quickActions: QuickAction[] = [
    ...(canManage ? [{ label: "Edit profile", icon: Pencil, onClick: () => onEdit(doctor) }] : []),
    { label: "Running late", icon: Clock, onClick: () => onRunningLate(doctor) },
    ...(canManage
      ? [
          {
            label: doctor.is_active ? "Mark unavailable" : "Mark available",
            icon: Power,
            onClick: () => onToggleActive(doctor),
            disabled: togglingId === doctor.id,
          },
        ]
      : []),
    {
      label: "Send message",
      icon: MessageCircle,
      disabled: true,
      title: "Coming soon — no doctor-facing internal messaging exists yet",
    },
    ...(canManage && !doctor.login_staff_id
      ? [{ label: "Create login", icon: KeyRound, onClick: () => onCreateLogin(doctor) }]
      : []),
    ...(canManage && doctor.login_staff_id
      ? [{ label: "Reset login access", icon: KeyRound, onClick: () => onResetPassword(doctor) }]
      : []),
    // Manage/attendance/leave history are all tied to this doctor's own
    // staff login/identity (login_staff_id), not their doctors.id -- same
    // field Create/Reset login above already branches on -- so there's
    // simply nothing to show for a doctor with no login yet.
    ...(canManageLeave && doctor.login_staff_id
      ? [{ label: "Manage leave", icon: CalendarClock, onClick: () => onManageLeave(doctor) }]
      : []),
    ...(canViewAttendance && doctor.login_staff_id
      ? [
          {
            label: "Attendance history",
            icon: History,
            onClick: () => onViewAttendanceHistory(doctor),
          },
        ]
      : []),
    ...(canViewLeaveHistory && doctor.login_staff_id
      ? [{ label: "Leave history", icon: CalendarDays, onClick: () => onViewLeaveHistory(doctor) }]
      : []),
  ];

  return (
    <Card className="p-space-4">
      <div className="mb-space-4 gap-space-3 flex items-center">
        <span
          className={cn(
            "flex h-16 w-16 shrink-0 items-center justify-center rounded-full text-[20px] font-bold",
            AVATAR_TINTS[index % AVATAR_TINTS.length],
          )}
        >
          {initials(doctor.name)}
        </span>
        <div className="flex min-w-0 flex-1 flex-col justify-center">
          <div className="gap-space-2 flex flex-wrap items-baseline">
            <p className="text-ink-900 truncate text-[15px] font-bold">{doctor.name}</p>
            <span
              className={cn(
                "px-space-2 shrink-0 rounded-full py-0.5 text-[11px] font-semibold",
                doctor.is_active ? "bg-success-tint text-success" : "text-ink-600 bg-black/4",
              )}
            >
              {doctor.is_active ? "Available" : "Unavailable"}
            </span>
          </div>
          {doctor.qualification && (
            <p className="text-ink-600 mt-0.5 truncate text-[12.5px]">
              Qualification : <span className="font-bold">{doctor.qualification}</span>
            </p>
          )}
        </div>
      </div>

      <div className="space-y-space-2 border-line pt-space-3 border-t">
        <DetailRow icon={IdCard} label="Employee ID" value={doctor.employee_id || "—"} />
        <DetailRow icon={Building2} label="Department" value={doctor.department_name} />
        <DetailRow
          icon={CalendarClock}
          label="Experience"
          value={doctor.years_experience != null ? `${doctor.years_experience} years` : "—"}
        />
        <DetailRow icon={Phone} label="Phone" value={doctor.phone || "—"} />
        <DetailRow icon={Mail} label="Login email" value={doctor.login_email || "No login yet"} />
        <DetailRow icon={MapPin} label="Address" value={doctor.location || "—"} />
        {/* <DetailRow
          icon={Calendar}
          label="Joined"
          value={doctor.created_at ? formatDate(doctor.created_at) : "—"}
        /> */}
      </div>

      {/* Same 4-tile-card grid StaffDetailPanel.tsx uses (Shift hours/
          Attendance status/Reports to/Leave balance) -- doctors get the
          equivalent 4: Working hours, Total appointments, Reports to
          (same staff_details.reports_to_id every other role already has --
          a doctor with a login can be assigned one too), Leave balance. */}
      <div className="mt-space-3 gap-space-2 grid grid-cols-2">
        <div className="border-line bg-paper p-space-3 rounded-md border">
          <p className="mb-space-1 text-ink-400 text-[11px] font-semibold">Working hours</p>
          <p className="text-ink-900 text-[13px] font-bold">
            {doctor.working_days.length > 0 ? formatWorkingDays(doctor.working_days) : "—"}
          </p>
          <p className="text-ink-600 text-[11.5px]">{hours || ""}</p>
        </div>
        <div className="border-line bg-paper p-space-3 rounded-md border">
          <p className="mb-space-1 gap-space-1 text-ink-400 flex items-center text-[11px] font-semibold">
            <CalendarCheck size={12} /> Total appointments
          </p>
          <p className="text-ink-900 text-[13px] font-bold">{doctor.total_appointments}</p>
        </div>
        <div className="border-line bg-paper p-space-3 rounded-md border">
          <p className="mb-space-1 gap-space-1 text-ink-400 flex items-center text-[11px] font-semibold">
            <Building2 size={12} /> Reports to
          </p>
          <p className="text-ink-900 truncate text-[13px] font-bold">
            {doctor.reports_to_name || "—"}
          </p>
        </div>
        <div className="border-line bg-paper p-space-3 rounded-md border">
          <p className="mb-space-1 text-ink-400 text-[11px] font-semibold">Leave balance</p>
          {doctor.leave_balance_total != null ? (
            <>
              <p className="text-ink-900 text-[13px] font-bold">
                {doctor.leave_balance_total - (doctor.leave_balance_used ?? 0)} /{" "}
                {doctor.leave_balance_total} days
              </p>
              <p className="text-ink-600 text-[11.5px]">remaining this year</p>
            </>
          ) : (
            <>
              <p className="text-ink-400 text-[13px] font-bold">—</p>
              <p className="text-ink-400 text-[11.5px]">No login yet</p>
            </>
          )}
        </div>
      </div>

      <div className="mt-space-4 border-line pt-space-3 border-t">
        <p className="text-label mb-space-2 text-ink-900 font-bold">Quick actions</p>
        <QuickActionList actions={quickActions} columns={2} size="sm" />
      </div>
    </Card>
  );
}
