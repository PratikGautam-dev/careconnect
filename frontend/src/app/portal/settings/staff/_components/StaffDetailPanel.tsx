"use client";

import type { LucideIcon } from "lucide-react";
import { Building2, Calendar, CalendarPlus, History, KeyRound, Mail, MapPin, Pencil, Phone } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { QuickActionList, type QuickAction } from "@/components/portal/QuickActions";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/formatDate";
import type { AttendanceStatus } from "@/hooks/useStaffManagement";
import { AVATAR_TINTS, ATTENDANCE_LABELS, ROLE_LABELS, SHIFT_LABELS, initials, type StaffRow } from "./staff-columns";

function DetailRow({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-space-3 text-[13px]">
      <span className="flex items-center gap-space-2 text-ink-400">
        <Icon size={14} className="shrink-0" /> {label}
      </span>
      <span className="truncate text-right font-medium text-ink-900">{value}</span>
    </div>
  );
}

const ATTENDANCE_TEXT: Record<AttendanceStatus, string> = {
  present: "text-success", on_leave: "text-error", half_day: "text-brand-600",
};
const ALL_ATTENDANCE_STATUSES: AttendanceStatus[] = ["present", "on_leave", "half_day"];

function staffDisplayId(id: number): string {
  return `ST${String(id).padStart(3, "0")}`;
}

type Props = {
  staff: StaffRow | null;
  index: number;
  canManage: boolean;
  onResetPassword: (staff: StaffRow) => void;
  onEdit: (staff: StaffRow) => void;
  onSetAttendance: (staff: StaffRow, status: AttendanceStatus) => void;
};

/** Right-rail "selected staff" profile card -- every field here is real
 * (staff_details/identities, migration 20260911174439) except Leave
 * balance, which stays an honest "not tracked yet" placeholder -- leave
 * tracking/workflow is explicitly out of scope for now (confirmed with the
 * user), unlike everything else on this card. */
export function StaffDetailPanel({ staff, index, canManage, onResetPassword, onEdit, onSetAttendance }: Props) {
  if (!staff) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-center text-[13px] text-ink-400">Select a staff member to view their profile.</p>
      </Card>
    );
  }

  const shiftLabel = staff.shift ? SHIFT_LABELS[staff.shift] : null;
  const shiftName = shiftLabel?.split(" (")[0] ?? "—";
  const shiftHours = shiftLabel?.match(/\((.+)\)/)?.[1] ?? "";

  const quickActions: QuickAction[] = [
    { label: "Apply leave", icon: CalendarPlus, disabled: true, title: "Coming soon — no leave workflow exists yet" },
    { label: "View leave history", icon: History, disabled: true, title: "Coming soon — no leave workflow exists yet" },
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
        <p className="text-[15px] font-bold text-ink-900">{staff.name}</p>
        <p className="text-[12px] text-ink-400">Staff ID: {staffDisplayId(staff.id)}</p>
        <p className="text-[12px] text-ink-400">
          {ROLE_LABELS[staff.role]} · {staff.department_name || "No department set"}
        </p>
      </div>

      <div className="space-y-space-2 border-t border-line pt-space-3">
        <DetailRow icon={Mail} label="Email" value={staff.email} />
        <DetailRow icon={Phone} label="Phone" value={staff.phone || "—"} />
        <DetailRow icon={MapPin} label="Location" value={staff.address || "—"} />
        <DetailRow icon={Calendar} label="Joined" value={staff.created_at ? formatDate(staff.created_at) : "—"} />
      </div>

      <div className="mt-space-3 grid grid-cols-2 gap-space-2">
        <div className="rounded-md border border-line bg-paper p-space-3">
          <p className="mb-space-1 text-[11px] font-semibold text-ink-400">Current shift</p>
          <p className="text-[13px] font-bold text-ink-900">{shiftName}</p>
          <p className="text-[11.5px] text-ink-600">{shiftHours}</p>
        </div>
        <div className="rounded-md border border-line bg-paper p-space-3">
          <p className="mb-space-1 text-[11px] font-semibold text-ink-400">Attendance status</p>
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
                  className="rounded bg-black/4 px-space-1 py-0.5 text-[10px] font-semibold text-ink-600 hover:bg-black/8"
                >
                  Mark {ATTENDANCE_LABELS[s]}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-space-2 grid grid-cols-2 gap-space-2">
        <div className="rounded-md border border-line bg-paper p-space-3">
          <p className="mb-space-1 text-[11px] font-semibold text-ink-400">Leave balance</p>
          <p className="text-[13px] font-bold text-ink-400">—</p>
          <p className="text-[11.5px] text-ink-400">Not tracked yet</p>
        </div>
        <div className="rounded-md border border-line bg-paper p-space-3">
          <p className="mb-space-1 flex items-center gap-space-1 text-[11px] font-semibold text-ink-400">
            <Building2 size={12} /> Reports to
          </p>
          <p className="truncate text-[13px] font-bold text-ink-900">{staff.reports_to_name || "—"}</p>
        </div>
      </div>

      <p className="text-hint mt-space-2">Leave balance/history isn&apos;t tracked in this app yet. Everything else on this card is real.</p>

      <div className="mt-space-4 border-t border-line pt-space-3">
        <p className="text-label mb-space-2 font-bold text-ink-900">Quick Actions</p>
        <QuickActionList actions={quickActions} />
      </div>
    </Card>
  );
}
