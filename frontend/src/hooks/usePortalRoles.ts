import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch, type StaffRole } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";

export type Action = "view" | "write" | "delete";
export type PagePerms = Record<Action, boolean>;
export type Matrix = Record<StaffRole, Record<string, PagePerms>>;

/** Roles & Permissions redesign: "Number of Users"/"Total Users"/"Active
 * Roles" stat tiles need real per-role staff counts -- GET /api/portal/staff
 * is the same directory the Staff page reads, just narrowed here to the two
 * fields these tiles actually need (role, is_active), not the full
 * StaffMember shape useStaffManagement owns. */
type StaffCounts = { total: number; byRole: Record<StaffRole, number>; activeByRole: Record<StaffRole, number> };
const EMPTY_COUNTS: StaffCounts = {
  total: 0,
  byRole: { admin: 0, receptionist: 0, doctor: 0 },
  activeByRole: { admin: 0, receptionist: 0, doctor: 0 },
};

/** Loads + owns every mutation on the /portal/settings/roles permission
 * matrix -- one optimistic-update PUT per checkbox toggle, rolled back on
 * failure. */
export function usePortalRoles(canView: boolean) {
  const router = useRouter();
  const [matrix, setMatrix] = useState<Matrix | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [staffCounts, setStaffCounts] = useState<StaffCounts>(EMPTY_COUNTS);
  // Tracks the single cell currently in flight, e.g. "admin:staff:write", so
  // only that checkbox shows a pending state while its PUT resolves.
  const [savingCell, setSavingCell] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/portal/roles/permissions");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setMatrix((result.data as { permissions: Matrix }).permissions);
  }, [router]);

  const loadStaffCounts = useCallback(async () => {
    // GET /api/portal/staff returns a bare array (see list_staff()'s own
    // docstring) and deliberately EXCLUDES doctors -- they have their own
    // directory/page. So the doctor role's count comes from
    // GET /api/portal/doctors instead, same is_active flag, just a
    // differently-shaped response ({ doctors: [...] } there, not a bare
    // array). Both fetched in parallel and fail open independently -- a
    // role without "staff" or "doctors" view permission still gets to see
    // the roles page's own matrix, just with that one role's count at 0
    // (these are stat-tile decoration, not the page's actual read/write
    // surface).
    const [staffResult, doctorsResult] = await Promise.all([
      staffFetch("/api/portal/staff"),
      staffFetch("/api/portal/doctors"),
    ]);
    const byRole: Record<StaffRole, number> = { admin: 0, receptionist: 0, doctor: 0 };
    const activeByRole: Record<StaffRole, number> = { admin: 0, receptionist: 0, doctor: 0 };
    let total = 0;
    if (staffResult.ok) {
      const staff = staffResult.data as { role: StaffRole; is_active: boolean }[];
      for (const s of staff) {
        byRole[s.role] += 1;
        if (s.is_active) activeByRole[s.role] += 1;
      }
      total += staff.length;
    }
    if (doctorsResult.ok) {
      // Only doctors with an actual staff login (login_staff_id set) count
      // as a "doctor role" user here -- a doctor row with no login yet
      // (get_all_doctors_for_hospital()'s own outer-joined login_* fields,
      // null until "Create login" is used) has no role/permissions at all,
      // so counting it would overstate how many people actually hold this
      // role today. "Active" here is the LOGIN's own active flag
      // (login_active) -- deliberately not the doctor row's own is_active
      // (that's the bookable Available/Unavailable toggle, a different,
      // unrelated concept from whether this person's account is enabled).
      const doctors = (doctorsResult.data as { doctors: { login_staff_id: number | null; login_active: boolean | null }[] }).doctors;
      const withLogin = doctors.filter((d) => d.login_staff_id != null);
      byRole.doctor = withLogin.length;
      activeByRole.doctor = withLogin.filter((d) => d.login_active).length;
      total += withLogin.length;
    }
    setStaffCounts({ total, byRole, activeByRole });
  }, []);

  useEffect(() => {
    if (canView) {
      load();
      loadStaffCounts();
    }
  }, [canView, load, loadStaffCounts]);

  async function handleToggle(role: StaffRole, pageKey: string, action: Action, next: boolean) {
    if (!matrix) return;
    const cellKey = `${role}:${pageKey}:${action}`;
    const prevCell = matrix[role][pageKey];
    const nextCell = { ...prevCell, [action]: next };
    setMatrix({ ...matrix, [role]: { ...matrix[role], [pageKey]: nextCell } });
    setSavingCell(cellKey);
    const result = await staffFetch("/api/portal/roles/permissions", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      // Backend contract (portal/routes/roles.py's PermissionsUpdatePayload)
      // is a batch of updates, even for a single-cell toggle like this one --
      // an earlier version of this call sent the fields flat/unwrapped,
      // which parsed fine (Pydantic ignores unknown fields) but always hit
      // the route's "no updates provided" 400, since `updates` defaulted to
      // an empty list.
      body: JSON.stringify({
        updates: [{
          role,
          page_key: pageKey,
          can_view: nextCell.view,
          can_write: nextCell.write,
          can_delete: nextCell.delete,
        }],
      }),
    });
    setSavingCell(null);
    if (!result.ok) {
      // Roll back on failure -- optimistic update kept the UI responsive
      // (this can be a lot of clicking through a 8x9 grid) but must not
      // silently drift from what the backend actually has stored.
      setMatrix({ ...matrix, [role]: { ...matrix[role], [pageKey]: prevCell } });
      if (result.unauthorized) {
        router.push("/portal/login");
      } else {
        setError(result.error);
        toast.error("Couldn't update permission", result.error);
      }
    }
  }

  return { matrix, error, savingCell, handleToggle, staffCounts };
}
