import { useCallback, useEffect, useState } from "react";
import { adminFetch } from "@/lib/adminAuth";

export type AuditEntry = {
  id: number;
  actor_level: string;
  hospital_id: number | null;
  hospital_name: string | null;
  actor_label: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  before_value: Record<string, unknown> | null;
  after_value: Record<string, unknown> | null;
  created_at: string;
};

/** Loads the /admin/audit-log list -- hospitalIdParam/levelFilter are owned
 * by the page (hospitalIdParam comes from the URL's ?hospital_id= query
 * param via useSearchParams(), a routing concern this hook stays out of). */
export function useAuditLog(hospitalIdParam: string | null, levelFilter: "" | "platform_admin" | "portal") {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const query = new URLSearchParams();
    if (hospitalIdParam) query.set("hospital_id", hospitalIdParam);
    if (levelFilter) query.set("actor_level", levelFilter);
    const result = await adminFetch(`/api/admin/audit-log?${query.toString()}`);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — refresh to sign in again." : result.error);
      return;
    }
    setEntries((result.data as { entries: AuditEntry[] }).entries);
  }, [hospitalIdParam, levelFilter]);

  useEffect(() => {
    load();
  }, [load]);

  return { entries, error };
}
