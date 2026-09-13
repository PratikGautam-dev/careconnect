import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import { useDepartments } from "@/hooks/useDepartments";
import type { StaffMember } from "@/hooks/useStaffManagement";
import type { StaffOption } from "@/hooks/useAddStaff";
import type { WorkingScheduleValue } from "@/components/portal/WorkingScheduleFields";

const EMPTY_SCHEDULE: WorkingScheduleValue = { working_days: [], shifts: [{ start: "", end: "" }], breaks: [] };

function toRange(s: string) {
  const [start, end] = s.split("-");
  return { start, end };
}

/** Owns the "Edit staff details" dialog's own form state + submit --
 * mirrors useAddStaff's self-contained shape, but pre-fills from an
 * existing StaffMember instead of starting blank, and PATCHes rather than
 * POSTs. Name/phone/address/schedule/reports_to_id are always included in
 * the PATCH body (even if unchanged) since this is a full edit form, not a
 * per-field autosave; department_id is omitted entirely for a doctor-role
 * row (their department comes from the linked doctor profile, not this
 * field -- see portal/routes/staff.py's own check for why sending it at
 * all would 400). */
export function useEditStaff(staff: StaffMember | null, onOpenChange: (open: boolean) => void, onSaved?: () => void) {
  const router = useRouter();
  const open = staff !== null;
  const departments = useDepartments(open);
  const [staffOptions, setStaffOptions] = useState<StaffOption[]>([]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [schedule, setSchedule] = useState<WorkingScheduleValue>(EMPTY_SCHEDULE);
  const [reportsToId, setReportsToId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const loadStaffOptions = useCallback(async () => {
    // GET /api/portal/staff/options, not GET /api/portal/staff -- see
    // useAddStaff's own note; this picker needs every role, including
    // doctors, unlike the Staff page's own directory.
    const result = await staffFetch("/api/portal/staff/options");
    if (!result.ok) return;
    setStaffOptions((result.data as StaffOption[]) || []);
  }, []);

  useEffect(() => {
    if (!staff) return;
    setName(staff.name);
    setPhone(staff.phone || "");
    setAddress(staff.address || "");
    setDepartmentId(staff.department_id || "");
    const shifts = (staff.working_hours || []).map(toRange);
    setSchedule({
      working_days: staff.working_days || [],
      shifts: shifts.length > 0 ? shifts : [{ start: "", end: "" }],
      breaks: (staff.breaks || []).map(toRange),
    });
    setReportsToId(staff.reports_to_id ? String(staff.reports_to_id) : "");
    setFormError(null);
    loadStaffOptions();
  }, [staff, loadStaffOptions]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!staff) return;
    setSaving(true);
    setFormError(null);
    const working_hours = schedule.shifts.filter((s) => s.start && s.end).map((s) => `${s.start}-${s.end}`);
    const breaks = schedule.breaks.filter((b) => b && b.start && b.end).map((b) => `${b.start}-${b.end}`);
    const result = await staffFetch(`/api/portal/staff/${staff.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        phone: phone || null,
        address: address || null,
        ...(!staff.is_doctor_role ? { department_id: departmentId || null } : {}),
        working_days: schedule.working_days,
        working_hours,
        breaks,
        reports_to_id: reportsToId ? Number(reportsToId) : null,
      }),
    });
    setSaving(false);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else {
        setFormError(result.error);
        toast.error("Couldn't update staff member", result.error);
      }
      return;
    }
    toast.success("Staff details updated");
    onOpenChange(false);
    onSaved?.();
  }

  return {
    departments, staffOptions,
    name, setName, phone, setPhone, address, setAddress, departmentId, setDepartmentId, schedule, setSchedule,
    reportsToId, setReportsToId,
    formError, saving, handleSave,
  };
}
