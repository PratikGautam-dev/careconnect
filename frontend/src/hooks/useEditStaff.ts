import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import { useDepartments } from "@/hooks/useDepartments";
import type { Shift, StaffMember } from "@/hooks/useStaffManagement";
import type { StaffOption } from "@/hooks/useAddStaff";

/** Owns the "Edit staff details" dialog's own form state + submit --
 * mirrors useAddStaff's self-contained shape, but pre-fills from an
 * existing StaffMember instead of starting blank, and PATCHes rather than
 * POSTs. Name/phone/address/shift/reports_to_id are always included in the
 * PATCH body (even if unchanged) since this is a full edit form, not a
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
  const [shift, setShift] = useState<Shift | "">("");
  const [reportsToId, setReportsToId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const loadStaffOptions = useCallback(async () => {
    const result = await staffFetch("/api/portal/staff");
    if (!result.ok) return;
    setStaffOptions((result.data as StaffOption[]) || []);
  }, []);

  useEffect(() => {
    if (!staff) return;
    setName(staff.name);
    setPhone(staff.phone || "");
    setAddress(staff.address || "");
    setDepartmentId(staff.department_id || "");
    setShift(staff.shift || "");
    setReportsToId(staff.reports_to_id ? String(staff.reports_to_id) : "");
    setFormError(null);
    loadStaffOptions();
  }, [staff, loadStaffOptions]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!staff) return;
    setSaving(true);
    setFormError(null);
    const result = await staffFetch(`/api/portal/staff/${staff.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        phone: phone || null,
        address: address || null,
        ...(staff.role !== "doctor" ? { department_id: departmentId || null } : {}),
        shift: shift || null,
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
    name, setName, phone, setPhone, address, setAddress, departmentId, setDepartmentId, shift, setShift,
    reportsToId, setReportsToId,
    formError, saving, handleSave,
  };
}
