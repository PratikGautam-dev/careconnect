"use client";

import type { LucideIcon } from "lucide-react";
import {
  Building2,
  Calendar,
  CalendarCheck,
  CalendarClock,
  CalendarPlus,
  History,
  IdCard,
  KeyRound,
  Mail,
  MapPin,
  Pencil,
  Phone,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { QuickActionList, type QuickAction } from "@/components/portal/QuickActions";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/formatDate";
import { formatWorkingDays, formatWorkingHours } from "@/lib/formatSchedule";
import type { AttendanceStatus } from "@/hooks/useStaffManagement";
import { AVATAR_TINTS, ATTENDANCE_LABELS, initials, type StaffRow } from "./staff-columns";

function DetailRow({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
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

const ATTENDANCE_TEXT: Record<AttendanceStatus, string> = {
  present: "text-success",
  on_leave: "text-error",
  half_day: "text-brand-600",
};
const ALL_ATTENDANCE_STATUSES: AttendanceStatus[] = ["present", "on_leave", "half_day"];

function staffDisplayId(id: number): string {
  return `ST${String(id).padStart(3, "0")}`;
}

type Props = {
  staff: StaffRow | null;
  index: number;
  canManage: boolean;
  canViewAttendance: boolean;
  canViewLeaveHistory: boolean;
  canManageLeave: boolean;
  onResetPassword: (staff: StaffRow) => void;
  onEdit: (staff: StaffRow) => void;
  onSetAttendance: (staff: StaffRow, status: AttendanceStatus) => void;
  onViewAttendanceHistory: (staff: StaffRow) => void;
  onViewLeaveHistory: (staff: StaffRow) => void;
  onManageLeave: (staff: StaffRow) => void;
};

/** Right-rail "selected staff" profile card -- every field here is real,
 * including Leave balance. "Manage leave" opens NewLeaveRequestDialog in
 * "on behalf of" mode (POST .../leave-requests/staff/{id}), auto-approved
 * immediately -- gated by "leave_requests" write, same permission the
 * review queue itself requires. */
export function StaffDetailPanel({
  staff,
  index,
  canManage,
  canViewAttendance,
  canViewLeaveHistory,
  canManageLeave,
  onResetPassword,
  onEdit,
  onSetAttendance,
  onViewAttendanceHistory,
  onViewLeaveHistory,
  onManageLeave,
}: Props) {
  if (!staff) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-ink-400 text-center text-[13px]">
          Select a staff member to view their profile.
        </p>
      </Card>
    );
  }

  // Staff schedule feature -- same formatWorkingDays/formatWorkingHours
  // display DoctorDetailPanel's own "Consulting hours" box uses.
  const scheduleDays = staff.working_days.length > 0 ? formatWorkingDays(staff.working_days) : null;
  const scheduleHours = formatWorkingHours(staff.working_hours);

  const quickActions: QuickAction[] = [
    ...(canManageLeave
      ? [{ label: "Manage leave", icon: CalendarPlus, onClick: () => onManageLeave(staff) }]
      : []),
    ...(canViewLeaveHistory
      ? [{ label: "View leave history", icon: History, onClick: () => onViewLeaveHistory(staff) }]
      : []),
    ...(canViewAttendance
      ? [
          {
            label: "Attendance history",
            icon: CalendarCheck,
            onClick: () => onViewAttendanceHistory(staff),
          },
        ]
      : []),
    ...(canManage
      ? [
          { label: "Edit staff details", icon: Pencil, onClick: () => onEdit(staff) },
          { label: "Reset login access", icon: KeyRound, onClick: () => onResetPassword(staff) },
        ]
      : []),
  ];

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex flex-col items-center text-center">
        <span
          className={cn(
            "mb-space-2 flex h-16 w-16 items-center justify-center rounded-full text-[20px] font-bold",
            AVATAR_TINTS[index % AVATAR_TINTS.length],
          )}
        >
          {initials(staff.name)}
        </span>
        <p className="text-ink-900 text-[15px] font-bold">{staff.name}</p>
        <p className="text-ink-400 text-[12px]">Staff ID: {staffDisplayId(staff.id)}</p>
        <p className="text-ink-400 text-[12px]">
          {staff.role_name} · {staff.department_name || "No department set"}
        </p>
      </div>

      <div className="space-y-space-2 border-line pt-space-3 border-t">
        <DetailRow icon={Mail} label="Email" value={staff.email} />
        <DetailRow icon={Phone} label="Phone" value={staff.phone || "—"} />
        <DetailRow icon={MapPin} label="Location" value={staff.address || "—"} />
        <DetailRow
          icon={Calendar}
          label="Joined"
          value={staff.created_at ? formatDate(staff.created_at) : "—"}
        />
        {/* Employee ID auto-numbering feature -- "—" for a doctor-role row,
            whose employee id lives on its linked doctors row instead. */}
        <DetailRow icon={IdCard} label="Employee ID" value={staff.employee_id || "—"} />
      </div>

      {/* Uniform 2x2 tile grid: Shift hours/Attendance status/Reports to/
          Leave balance, matching DoctorDetailPanel.tsx's own 4-tile grid. */}
      <div className="mt-space-3 gap-space-2 grid grid-cols-2">
        <div className="border-line bg-paper p-space-3 rounded-md border">
          <p className="mb-space-1 gap-space-1 text-ink-400 flex items-center text-[11px] font-semibold">
            <CalendarClock size={12} /> Shift hours
          </p>
          <p className="text-ink-900 text-[13px] font-bold">{scheduleDays || "—"}</p>
          <p className="text-ink-600 text-[11.5px]">{scheduleHours || ""}</p>
        </div>
        <div className="border-line bg-paper p-space-3 rounded-md border">
          <p className="mb-space-1 text-ink-400 text-[11px] font-semibold">Attendance status</p>
          <p className={cn("text-[13px] font-bold", ATTENDANCE_TEXT[staff.attendance_status])}>
            {ATTENDANCE_LABELS[staff.attendance_status]}
          </p>
          {canManage && (
            <div className="mt-space-1 flex flex-wrap gap-1">
              {ALL_ATTENDANCE_STATUSES.filter((s) => s !== staff.attendance_status).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => onSetAttendance(staff, s)}
                  className="px-space-1 text-ink-600 rounded bg-black/4 py-0.5 text-[10px] font-semibold hover:bg-black/8"
                >
                  Mark {ATTENDANCE_LABELS[s]}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="border-line bg-paper p-space-3 rounded-md border">
          <p className="mb-space-1 gap-space-1 text-ink-400 flex items-center text-[11px] font-semibold">
            <Building2 size={12} /> Reports to
          </p>
          <p className="text-ink-900 truncate text-[13px] font-bold">
            {staff.reports_to_name || "—"}
          </p>
        </div>
        <div className="border-line bg-paper p-space-3 rounded-md border">
          <p className="mb-space-1 text-ink-400 text-[11px] font-semibold">Leave balance</p>
          {staff.leave_balance_total != null ? (
            <>
              <p className="text-ink-900 text-[13px] font-bold">
                {staff.leave_balance_total - (staff.leave_balance_used ?? 0)} /{" "}
                {staff.leave_balance_total} days
              </p>
              <p className="text-ink-600 text-[11.5px]">remaining this year</p>
            </>
          ) : (
            <>
              <p className="text-ink-400 text-[13px] font-bold">—</p>
              <p className="text-ink-400 text-[11.5px]">Not tracked for this role</p>
            </>
          )}
        </div>
      </div>

      <p className="text-hint mt-space-2">
        Leave balance is real (Leave Requests page, Settings &gt; Leave policy).
      </p>

      <div className="mt-space-4 border-line pt-space-3 border-t">
        <p className="text-label mb-space-2 text-ink-900 font-bold">Quick Actions</p>
        <QuickActionList actions={quickActions} columns={2} />
      </div>
    </Card>
  );
}
