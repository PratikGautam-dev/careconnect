import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { unwrapPortalResult } from "@/lib/portalMutation";

export type Department = { id: string; name: string };
// login_staff_id/login_email/login_active come from an outer join to
// staff_details/identities (db.get_all_doctors_for_hospital()) -- all three
// are null when this doctor has no staff login yet. Replaces the old
// dedicated doctors.email/password_hash columns (dropped, migration
// 20260911190251) -- a doctor's login now always goes through the unified
// staff login (Staff page or this page's own "Create login" action).
export type Doctor = {
  id: string;
  department_id: string;
  department_name: string;
  name: string;
  specialization: string | null;
  is_active: boolean;
  qualification: string | null;
  years_experience: number | null;
  working_days: string[];
  working_hours: string[];
  // Mandatory; location stays optional.
  phone: string;
  // Server-generated (EMP-DC-NNNNN), never part of the editable Add/Edit
  // form; read-only display only (doctors-columns.tsx, DoctorDetailPanel.tsx).
  employee_id: string;
  location: string | null;
  login_staff_id: number | null;
  login_email: string | null;
  login_active: boolean | null;
  // Leave Requests migration (20260912065049) -- both null for a doctor
  // with no login yet (no identity to attach a leave request to).
  leave_balance_total: number | null;
  leave_balance_used: number | null;
  // Every appointment ever booked against this doctor, any status --
  // db.get_appointment_counts_by_doctor().
  total_appointments: number;
  // Same staff_details.reports_to_id -> identities join every other role
  // already gets on the Staff page -- null if this doctor has no login yet,
  // or has one but no reports-to set.
  reports_to_name: string | null;
};

type DoctorsResponse = {
  departments: Department[];
  doctors: Doctor[];
  on_leave_today_count: number;
};

export const DOCTORS_QUERY_KEY = ["portal-doctors"] as const;

/** Read-only: the /portal/doctors list, its department picker options, and
 * today's on-leave count -- all bundled off the one GET /api/portal/doctors
 * response (db.get_all_doctors_for_hospital()). Department CREATION/editing
 * lives entirely under /portal/settings' own Departments tab (confirmed
 * with the user) -- this hook only ever READS departments, to populate the
 * doctor list's own department column and the Add/Edit Doctor form's
 * department picker. Mutations (create/update/toggle-active/single-doctor
 * fetch) live in their own hooks below -- call this hook's `load()` after
 * one succeeds to refresh the list. */
export function useDoctors(ready: boolean) {
  const router = useRouter();

  const {
    data,
    error: queryError,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: DOCTORS_QUERY_KEY,
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/doctors");
      return unwrapPortalResult<DoctorsResponse>(router, result);
    },
  });

  return {
    departments: data?.departments ?? null,
    doctors: data?.doctors ?? [],
    onLeaveTodayCount: data?.on_leave_today_count ?? 0,
    error: queryError ? "Couldn't load doctors — try again." : null,
    isFetching,
    load: refetch,
  };
}

/** Fetches ONE doctor's full record (working days/hours/breaks/quotas --
 * useDoctors()' own list shape above doesn't carry these), by id. Modeled
 * as a mutation rather than a query since every caller wants it as a
 * one-shot, on-demand `await fetchDoctor(id)` -- populating the Add/Edit
 * Doctor form when "Edit" is clicked (doctors/page.tsx), or getting the
 * current full record before a doctor-reassign resubmit (Settings ->
 * Departments' "Assign doctor" flow, DepartmentsTab.tsx) -- not something
 * rendered directly off cache. */
export function useDoctor() {
  const router = useRouter();

  const { mutateAsync, isPending } = useMutation({
    mutationFn: async (doctorId: string) => {
      const result = await portalFetch(`/api/portal/doctors/${doctorId}`);
      return unwrapPortalResult<{ doctor: Record<string, unknown> }>(router, result).doctor;
    },
  });

  return { fetchDoctor: mutateAsync, isFetching: isPending };
}

// Same shape DoctorScheduleForm builds and POSTs -- kept as a plain object
// type (not imported from the form) since this is the wire payload, not the
// form's own draft-string state.
export type DoctorPayload = {
  department_id: string;
  name: string;
  specialization: string;
  qualification: string;
  years_experience: string;
  working_days: string[];
  working_hours: string[];
  slot_duration_minutes: string;
  breaks: string[];
  max_bookings_per_slot: string;
  daily_booking_limit: string;
  online_quota: string;
  walkin_quota: string;
  followup_duration_minutes: string;
  effective_from: string;
  phone: string;
  location: string;
};

/** POST /api/portal/doctors -- create. Caller should refetch useDoctors()'
 * list on success (its query key isn't invalidated automatically here, to
 * keep this hook a plain, single-purpose mutation). */
export function useCreateDoctor() {
  const router = useRouter();

  return useMutation({
    mutationFn: async (payload: DoctorPayload) => {
      const result = await portalFetch("/api/portal/doctors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapPortalResult<{ errors?: string[] }>(router, result);
    },
  });
}

/** POST /api/portal/doctors/{id} -- full-record update (same route both
 * "Edit doctor" and Settings -> Departments' "Assign doctor" reassign flow
 * use; the latter builds its own payload separately in DepartmentsTab.tsx
 * since it re-sends a fetched record's fields rather than a form's).
 * Caller should refetch useDoctors()' list on success. */
export function useUpdateDoctor() {
  const router = useRouter();

  return useMutation({
    mutationFn: async ({
      doctorId,
      payload,
    }: {
      doctorId: string;
      payload: DoctorPayload | Record<string, unknown>;
    }) => {
      const result = await portalFetch(`/api/portal/doctors/${doctorId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapPortalResult<{ errors?: string[] }>(router, result);
    },
  });
}

/** POST /api/portal/doctors/{id}/active -- mark available/unavailable.
 * Caller should refetch useDoctors()' list on success. */
export function useToggleDoctorActive() {
  const router = useRouter();

  return useMutation({
    mutationFn: async ({ doctorId, isActive }: { doctorId: string; isActive: boolean }) => {
      const result = await portalFetch(`/api/portal/doctors/${doctorId}/active`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: isActive }),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
}
