import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch, type StaffRole } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import { setStaffPasswordSchema } from "@/lib/validation/setStaffPassword";

export type AttendanceStatus = "present" | "on_leave" | "half_day";
export type Shift = "day" | "evening" | "night";

// Matches portal/routes/staff.py's _staff_row() -- department_id/
// department_name/reports_to_id/reports_to_name/phone/address/shift/
// attendance_status/created_at were all mocked client-side before; they're
// now real staff_details/identities columns (migration 20260911174439).
// leave_balance_total/used are real too (migration 20260912065049) --
// both null for an admin row, since the leave policy is doctor/
// receptionist only (confirmed with the user, admin approves leave rather
// than accruing an allowance). Leave request CREATION is still a later
// page -- see StaffDetailPanel's own note.
export type StaffMember = {
  id: number;
  name: string;
  email: string;
  role: StaffRole;
  doctor_id: string | null;
  is_active: boolean;
  created_at: string | null;
  phone: string | null;
  address: string | null;
  shift: Shift | null;
  attendance_status: AttendanceStatus;
  department_id: string | null;
  department_name: string | null;
  reports_to_id: number | null;
  reports_to_name: string | null;
  leave_balance_total: number | null;
  leave_balance_used: number | null;
};

/** Loads + owns every mutation on /portal/settings/staff EXCEPT creating a
 * new staff member -- that form now lives in its own reusable
 * AddStaffDialog/useAddStaff, since it's also opened from the dashboard's
 * Quick Actions, not just this page. This hook keeps the staff list, the
 * active/inactive toggle, and the reset-password dialog. */
export function useStaffManagement(canView: boolean) {
  const router = useRouter();

  const [staff, setStaff] = useState<StaffMember[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const [resetPasswordTarget, setResetPasswordTarget] = useState<StaffMember | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [resetErrors, setResetErrors] = useState<string[]>([]);
  const [resetting, setResetting] = useState(false);

  const load = useCallback(async () => {
    // GET /api/portal/staff is the Staff page's own directory -- doctors
    // are excluded server-side (see that route's own docstring): they have
    // their own dedicated page + "Create login" action there, so a
    // role="doctor" staff_details row (needed purely so that login can
    // authenticate through the shared unified staff login) never shows up
    // as a row in THIS "hospital staff" list. The reports-to picker
    // (useAddStaff/useEditStaff) needs every role instead, so it calls the
    // separate GET /api/portal/staff/options endpoint.
    const result = await staffFetch("/api/portal/staff");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setStaff(result.data as StaffMember[]);
  }, [router]);

  useEffect(() => {
    if (!canView) return;
    load();
  }, [canView, load]);

  async function handleToggleActive(member: StaffMember) {
    setTogglingId(member.id);
    const result = await staffFetch(`/api/portal/staff/${member.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !member.is_active }),
    });
    setTogglingId(null);
    if (result.ok) {
      toast.success(member.is_active ? "Staff member deactivated" : "Staff member activated");
      load();
    } else if (result.unauthorized) {
      router.push("/portal/login");
    } else {
      toast.error("Couldn't update staff member", result.error);
    }
  }

  async function handleSetAttendance(member: StaffMember, attendanceStatus: AttendanceStatus) {
    const result = await staffFetch(`/api/portal/staff/${member.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ attendance_status: attendanceStatus }),
    });
    if (result.ok) {
      load();
    } else if (result.unauthorized) {
      router.push("/portal/login");
    } else {
      toast.error("Couldn't update attendance status", result.error);
    }
  }

  function openResetPassword(member: StaffMember) {
    setResetPasswordTarget(member);
    setNewPassword("");
    setConfirmPassword("");
    setResetErrors([]);
  }

  function closeResetPassword() {
    setResetPasswordTarget(null);
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    if (!resetPasswordTarget) return;

    const parsed = setStaffPasswordSchema.safeParse({ new_password: newPassword, confirm_password: confirmPassword });
    if (!parsed.success) {
      setResetErrors(parsed.error.issues.map((issue) => issue.message));
      return;
    }

    setResetting(true);
    setResetErrors([]);
    const result = await staffFetch(`/api/portal/staff/${resetPasswordTarget.id}/password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_password: parsed.data.new_password }),
    });
    setResetting(false);

    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else {
        setResetErrors([result.error]);
        toast.error("Couldn't reset password", result.error);
      }
      return;
    }
    toast.success(`Password reset for ${resetPasswordTarget.name}`);
    setResetPasswordTarget(null);
  }

  return {
    staff, error, togglingId, load,
    handleToggleActive, handleSetAttendance,
    resetPasswordTarget, newPassword, setNewPassword, confirmPassword, setConfirmPassword,
    resetErrors, resetting, openResetPassword, closeResetPassword, handleResetPassword,
  };
}
