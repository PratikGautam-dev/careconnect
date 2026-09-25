import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { staffFetch } from "@/lib/staffAuth";
import { unwrapPortalResult } from "@/lib/portalMutation";
import { setStaffPasswordSchema } from "@/lib/validation/setStaffPassword";
import type { Role } from "@/hooks/usePortalRoles";

// Matches portal/routes/staff.py's _staff_row() -- department_id/
// leave_balance_total/used are both null for an admin row, since the leave
// policy is doctor/receptionist only (admin approves leave rather than
// accruing an allowance).
export type StaffMember = {
  id: number;
  name: string;
  email: string;
  role_id: number;
  role_name: string;
  is_doctor_role: boolean;
  doctor_id: string | null;
  is_active: boolean;
  created_at: string | null;
  phone: string | null;
  address: string | null;
  // Staff schedule feature -- replaces the old shift enum with the same
  // comma-stored (already split into lists by _staff_row()) working_days/
  // working_hours/breaks model doctors already have.
  working_days: string[];
  working_hours: string[];
  breaks: string[];
  department_id: string | null;
  department_name: string | null;
  reports_to_id: number | null;
  reports_to_name: string | null;
  leave_balance_total: number | null;
  leave_balance_used: number | null;
  // Employee ID auto-numbering feature -- server-generated (EMP-ST-NNNNN)
  // for a non-doctor role; "" for a doctor-role row (its EMP-DC id lives on
  // the linked doctors row instead).
  employee_id: string;
};

export const STAFF_QUERY_KEY = ["portal-staff"] as const;

/** Read-only: the /portal/settings/staff directory. Doctors are excluded
 * server-side (see GET /api/portal/staff's own docstring): they have their
 * own dedicated page + "Create login" action there, so a role="doctor"
 * staff_details row (needed purely so that login can authenticate through
 * the shared unified staff login) never shows up as a row in THIS "hospital
 * staff" list. Mutations (create/update/toggle-active/reset-password) live
 * in their own hooks below -- call this hook's `load()` after one succeeds
 * to refresh the list. */
export function useStaff(canView: boolean) {
  const router = useRouter();

  const {
    data,
    error: queryError,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: STAFF_QUERY_KEY,
    enabled: canView,
    retry: false,
    queryFn: async () => {
      const result = await staffFetch("/api/portal/staff");
      return unwrapPortalResult<StaffMember[]>(router, result);
    },
  });

  return {
    staff: data ?? null,
    error: queryError ? "Couldn't load staff — try again." : null,
    isFetching,
    load: refetch,
  };
}

/** PATCH /api/portal/staff/{id} -- active/inactive toggle. Caller should
 * refetch useStaff()'s list on success. */
export function useToggleStaffActive() {
  const router = useRouter();

  return useMutation({
    mutationFn: async ({ staffId, isActive }: { staffId: number; isActive: boolean }) => {
      const result = await staffFetch(`/api/portal/staff/${staffId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: isActive }),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
}

/** POST /api/portal/staff/{id}/password -- admin-initiated reset. Field
 * validation (setStaffPasswordSchema) happens here so the caller's onError
 * can distinguish "didn't even try the request" from a server rejection,
 * same as every other mutation's isPortalMutationError() check. */
export function useResetStaffPassword() {
  const router = useRouter();

  return useMutation({
    mutationFn: async ({
      staffId,
      newPassword,
      confirmPassword,
    }: {
      staffId: number;
      newPassword: string;
      confirmPassword: string;
    }) => {
      const parsed = setStaffPasswordSchema.safeParse({
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      if (!parsed.success) {
        throw new Error(parsed.error.issues.map((issue) => issue.message).join(" "));
      }
      const result = await staffFetch(`/api/portal/staff/${staffId}/password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_password: parsed.data.new_password }),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
}

export type StaffOption = { id: number; name: string };

/** GET /api/portal/staff/options -- the "Reports to" picker's own list, not
 * the Staff page's own GET /api/portal/staff directory above (that one
 * excludes doctors; this picker still needs to offer a doctor as a valid
 * manager). Shared by the Add/Edit staff dialogs (useAddStaff/useEditStaff)
 * -- `enabled` is each dialog's own `open` state. */
export function useStaffOptions(enabled: boolean) {
  const { data, isFetching } = useQuery({
    queryKey: ["portal-staff-options"],
    enabled,
    retry: false,
    queryFn: async () => {
      const result = await staffFetch("/api/portal/staff/options");
      if (!result.ok) return [];
      return (result.data as StaffOption[]) || [];
    },
  });

  return { staffOptions: data ?? [], isFetching };
}

/** GET /api/portal/roles -- the Add Staff dialog's own role picker. Kept
 * separate from usePortalRoles.ts's own, much larger permissions-matrix
 * hook (Settings -> Roles page), which this dialog has no use for. */
export function useStaffRoleOptions(enabled: boolean) {
  const { data, isFetching } = useQuery({
    queryKey: ["portal-role-options"],
    enabled,
    retry: false,
    queryFn: async () => {
      const result = await staffFetch("/api/portal/roles");
      if (!result.ok) return [];
      return (result.data as { roles: Role[] }).roles;
    },
  });

  return { roles: data ?? [], isFetching };
}

// Wire payload both create and update share the bulk of -- kept separate
// (rather than one type with optional fields) since create requires
// email/password/role_id that update never sends.
export type StaffContactPayload = {
  phone?: string;
  address?: string;
  department_id?: string;
  working_days: string[];
  working_hours: string[];
  breaks: string[];
  reports_to_id?: number;
};

export type CreateStaffPayload = StaffContactPayload & {
  name: string;
  email: string;
  password: string;
  role_id: number;
  doctor_id?: string;
};

/** POST /api/portal/staff -- create. Caller should refetch useStaff()'s
 * list on success. */
export function useCreateStaffMember() {
  const router = useRouter();

  return useMutation({
    mutationFn: async (payload: CreateStaffPayload) => {
      const result = await staffFetch("/api/portal/staff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
}

export type UpdateStaffPayload = {
  name: string;
  phone: string | null;
  address: string | null;
  department_id?: string | null;
  working_days: string[];
  working_hours: string[];
  breaks: string[];
  reports_to_id: number | null;
};

/** PATCH /api/portal/staff/{id} -- full profile-field update ("Edit staff
 * details" dialog). Caller should refetch useStaff()'s list on success. */
export function useUpdateStaffMember() {
  const router = useRouter();

  return useMutation({
    mutationFn: async ({ staffId, payload }: { staffId: number; payload: UpdateStaffPayload }) => {
      const result = await staffFetch(`/api/portal/staff/${staffId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
}
