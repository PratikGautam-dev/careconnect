import { useState } from "react";
import { useDepartments } from "@/hooks/useDepartments";
import { isPortalMutationError } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";
import {
  useStaffOptions,
  useUpdateStaffMember,
  type StaffMember,
  type UpdateStaffPayload,
} from "@/hooks/useStaff";
import type { WorkingScheduleValue } from "@/components/portal/WorkingScheduleFields";

const EMPTY_SCHEDULE: WorkingScheduleValue = {
  working_days: [],
  shifts: [{ start: "", end: "" }],
  breaks: [],
};

function toRange(s: string) {
  const [start, end] = s.split("-");
  return { start, end };
}

function fieldsFromStaff(staff: StaffMember) {
  const shifts = (staff.working_hours || []).map(toRange);
  return {
    name: staff.name,
    phone: staff.phone || "",
    address: staff.address || "",
    departmentId: staff.department_id || "",
    schedule: {
      working_days: staff.working_days || [],
      shifts: shifts.length > 0 ? shifts : [{ start: "", end: "" }],
      breaks: (staff.breaks || []).map(toRange),
    } as WorkingScheduleValue,
    reportsToId: staff.reports_to_id ? String(staff.reports_to_id) : "",
  };
}

/** Owns the "Edit staff details" dialog's own form state + submit --
 * mirrors useAddStaff's self-contained shape, but pre-fills from an
 * existing StaffMember instead of starting blank, and PATCHes rather than
 * POSTs. Name/phone/address/schedule/reports_to_id are always included in
 * the PATCH body (even if unchanged) since this is a full edit form, not a
 * per-field autosave; department_id is omitted entirely for a doctor-role
 * row (their department comes from the linked doctor profile, not this
 * field -- see portal/routes/staff.py's own check for why sending it at
 * all would 400).
 *
 * Fields are seeded from `staff` during render (not a useEffect) -- React's
 * own "adjusting state when a prop changes" pattern -- since deriving state
 * from a changing prop inside an effect causes an extra render and trips
 * the set-state-in-effect lint rule. `staff` only ever changes at the
 * moment the dialog opens for a (possibly different) row, so re-seeding
 * whenever its id changes is exactly the open-with-fresh-data behavior the
 * old effect-based version had. */
export function useEditStaff(
  staff: StaffMember | null,
  onOpenChange: (open: boolean) => void,
  onSaved?: () => void,
) {
  const open = staff !== null;
  const departments = useDepartments(open);
  const { staffOptions } = useStaffOptions(open);
  const updateStaffMember = useUpdateStaffMember();

  const [seededStaffId, setSeededStaffId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [schedule, setSchedule] = useState<WorkingScheduleValue>(EMPTY_SCHEDULE);
  const [reportsToId, setReportsToId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  if (staff && staff.id !== seededStaffId) {
    setSeededStaffId(staff.id);
    const fields = fieldsFromStaff(staff);
    setName(fields.name);
    setPhone(fields.phone);
    setAddress(fields.address);
    setDepartmentId(fields.departmentId);
    setSchedule(fields.schedule);
    setReportsToId(fields.reportsToId);
    setFormError(null);
  } else if (!staff && seededStaffId !== null) {
    setSeededStaffId(null);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!staff) return;
    setFormError(null);
    const working_hours = schedule.shifts
      .filter((s) => s.start && s.end)
      .map((s) => `${s.start}-${s.end}`);
    const breaks = schedule.breaks
      .filter((b) => b && b.start && b.end)
      .map((b) => `${b.start}-${b.end}`);
    const payload: UpdateStaffPayload = {
      name,
      phone: phone || null,
      address: address || null,
      ...(!staff.is_doctor_role ? { department_id: departmentId || null } : {}),
      working_days: schedule.working_days,
      working_hours,
      breaks,
      reports_to_id: reportsToId ? Number(reportsToId) : null,
    };
    try {
      await updateStaffMember.mutateAsync({ staffId: staff.id, payload });
      toast.success("Staff details updated");
      onOpenChange(false);
      onSaved?.();
    } catch (err) {
      if (isPortalMutationError(err)) {
        setFormError(err.message);
        toast.error("Couldn't update staff member", err.message);
      }
    }
  }

  return {
    departments,
    staffOptions,
    name,
    setName,
    phone,
    setPhone,
    address,
    setAddress,
    departmentId,
    setDepartmentId,
    schedule,
    setSchedule,
    reportsToId,
    setReportsToId,
    formError,
    saving: updateStaffMember.isPending,
    handleSave,
  };
}
