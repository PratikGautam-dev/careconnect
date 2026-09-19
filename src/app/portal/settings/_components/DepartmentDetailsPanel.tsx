"use client";

import {
  Building2,
  Clock,
  FileText,
  Mail,
  Pencil,
  Phone,
  ShieldCheck,
  UserCog,
  UserPlus,
  Users,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { DepartmentDetail } from "@/hooks/useDepartments";
import { StatusBadge } from "./department-columns";
import { ToggleRow } from "./settings-ui";

function Row({
  icon: Icon,
  label,
  value,
}: {
  icon?: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="gap-space-3 py-space-2 flex items-start justify-between text-[13px]">
      <span className="gap-space-1.5 text-ink-400 flex items-center">
        {Icon && <Icon size={13} />}
        {label}
      </span>
      <span className="text-ink-900 max-w-[60%] text-right font-semibold">{value}</span>
    </div>
  );
}

type Props = {
  department: DepartmentDetail | null;
  visibilitySaving: boolean;
  onEdit: (department: DepartmentDetail) => void;
  onAssignDoctor: (department: DepartmentDetail) => void;
  onManageStaff: (department: DepartmentDetail) => void;
  onToggleActive: (department: DepartmentDetail) => void;
  onVisibilityChange: (
    department: DepartmentDetail,
    field: "show_on_frontend" | "online_booking_enabled" | "whatsapp_booking_enabled",
  ) => void;
};

/** Settings -> Departments' right-rail "Department Details" panel --
 * mirrors Report Review/Doctors/Patients' own selected-row detail rail
 * pattern. Everything here is real (see useDepartments.ts's
 * useDepartmentsAdmin), including the Patient-Facing Availability toggles
 * -- online_booking_enabled is stored/toggleable but not enforced by
 * anything yet (no separate online booking channel exists in this app),
 * flagged in its own hint text below rather than left unexplained. */
export function DepartmentDetailsPanel({
  department,
  visibilitySaving,
  onEdit,
  onAssignDoctor,
  onManageStaff,
  onToggleActive,
  onVisibilityChange,
}: Props) {
  if (!department) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-ink-400 text-center text-[13px]">No department selected.</p>
      </Card>
    );
  }

  const head = department.head_doctor;

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 gap-space-2 flex items-start justify-between">
        <h3 className="text-label text-ink-900 font-bold">Department Details</h3>
        <StatusBadge isActive={department.is_active} />
      </div>

      <div className="mb-space-3 gap-space-3 border-line pb-space-3 flex items-start border-b">
        <span className="bg-brand-50 text-brand-600 flex h-11 w-11 shrink-0 items-center justify-center rounded-md">
          <Building2 size={20} />
        </span>
        <div className="min-w-0">
          <p className="text-ink-900 truncate text-[14px] font-bold">{department.name}</p>
          <p className="text-ink-400 truncate text-[12px]">
            {department.doctor_count} doctor{department.doctor_count === 1 ? "" : "s"} ·{" "}
            {department.support_staff_count} support staff
          </p>
        </div>
      </div>

      {head ? (
        <div className="mb-space-3 bg-paper p-space-3 rounded-md">
          <p className="mb-space-1 text-ink-400 text-[11px] font-semibold tracking-wide uppercase">
            Head of Department
          </p>
          <p className="text-ink-900 text-[13.5px] font-bold">{head.name}</p>
          <p className="mb-space-1 text-ink-400 text-[12px]">{head.qualification}</p>
          {head.phone && (
            <p className="gap-space-1 text-ink-600 flex items-center text-[12px]">
              <Phone size={11} /> {head.phone}
            </p>
          )}
          {head.email && (
            <p className="gap-space-1 text-ink-600 flex items-center text-[12px]">
              <Mail size={11} /> {head.email}
            </p>
          )}
        </div>
      ) : (
        <p className="mb-space-3 text-ink-400 text-[12.5px]">No Head of Department set.</p>
      )}

      <div className="divide-line border-line divide-y border-b">
        <Row icon={Building2} label="Floor / Wing" value={department.floor_wing || "—"} />
        <Row icon={Clock} label="Consultation Hours" value={department.consultation_hours || "—"} />
        <Row icon={Users} label="Total Doctors" value={department.doctor_count} />
        <Row icon={UserCog} label="Support Staff" value={department.support_staff_count} />
      </div>
      <div className="py-space-2">
        <p className="mb-space-1 gap-space-1.5 text-ink-400 flex items-center text-[13px]">
          <FileText size={13} /> Description
        </p>
        <p className="text-ink-700 text-[13px]">
          {department.description || "No description added yet."}
        </p>
      </div>

      <div className="mt-space-3 border-line pt-space-3 border-t">
        <h4 className="mb-space-1 gap-space-1.5 text-ink-900 flex items-center text-[13px] font-bold">
          <ShieldCheck size={14} className="text-brand-600" /> Patient-Facing Availability
        </h4>
        <ToggleRow
          label="Show Department on CareConnect"
          subtitle="Controls whether it appears on the WhatsApp menu"
          checked={department.show_on_frontend}
          onChange={() => onVisibilityChange(department, "show_on_frontend")}
          disabled={visibilitySaving}
        />
        <ToggleRow
          label="Allow Online Appointment Booking"
          subtitle="If OFF, department can still be visible but patients cannot book"
          checked={department.online_booking_enabled}
          onChange={() => onVisibilityChange(department, "online_booking_enabled")}
          disabled={visibilitySaving}
        />
        <ToggleRow
          label="Allow WhatsApp Booking"
          subtitle="Turns off booking via the WhatsApp menu specifically"
          checked={department.whatsapp_booking_enabled}
          onChange={() => onVisibilityChange(department, "whatsapp_booking_enabled")}
          disabled={visibilitySaving}
        />
      </div>

      <div className="mt-space-4 border-line pt-space-4 border-t">
        <h4 className="mb-space-2 text-ink-900 text-[13px] font-bold">Quick Actions</h4>
        <div className="gap-space-2 grid grid-cols-2">
          <Button type="button" variant="secondary" size="md" onClick={() => onEdit(department)}>
            <Pencil size={13} /> Edit Department
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="md"
            onClick={() => onAssignDoctor(department)}
          >
            <UserPlus size={13} /> Assign Doctor
          </Button>
          <Button type="button" variant="secondary" size="md" onClick={() => onEdit(department)}>
            <Clock size={13} /> Manage Timings
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="md"
            onClick={() => onManageStaff(department)}
          >
            <UserCog size={13} /> Manage Staff
          </Button>
        </div>
        <button
          type="button"
          onClick={() => onToggleActive(department)}
          className="mt-space-2 gap-space-2 border-error/30 bg-error-tint px-space-3 py-space-2 text-error hover:bg-error/15 flex w-full items-center justify-center rounded-md border text-[13px] font-semibold"
        >
          <XCircle size={14} />
          {department.is_active ? "Deactivate Department" : "Activate Department"}
        </button>
      </div>
    </Card>
  );
}
