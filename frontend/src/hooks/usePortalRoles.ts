import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch, type StaffRole } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";

export type Action = "view" | "write" | "delete";
export type PagePerms = Record<Action, boolean>;
export type Matrix = Record<StaffRole, Record<string, PagePerms>>;

/** Loads + owns every mutation on the /portal/settings/roles permission
 * matrix -- one optimistic-update PUT per checkbox toggle, rolled back on
 * failure. */
export function usePortalRoles(canView: boolean) {
  const router = useRouter();
  const [matrix, setMatrix] = useState<Matrix | null>(null);
  const [error, setError] = useState<string | null>(null);
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

  useEffect(() => {
    if (canView) load();
  }, [canView, load]);

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

  return { matrix, error, savingCell, handleToggle };
}
