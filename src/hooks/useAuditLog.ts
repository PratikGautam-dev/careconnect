import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";

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
export function useAuditLog(
  hospitalIdParam: string | null,
  levelFilter: "" | "platform_admin" | "portal",
) {
  const { data: entries, error: queryError } = useQuery({
    queryKey: ["admin-audit-log", hospitalIdParam, levelFilter],
    retry: false,
    queryFn: async () => {
      const query = new URLSearchParams();
      if (hospitalIdParam) query.set("hospital_id", hospitalIdParam);
      if (levelFilter) query.set("actor_level", levelFilter);
      // This hook backs "latest N" widgets (subscriptions page's own
      // recent-activity panel), not a paginated view -- the route's default
      // page size is 50 (tuned for the real audit-log page's own table),
      // so ask for the wider pool this widget's own client-side slice/
      // filter (entity_type === "hospital_subscription") needs to find
      // enough matching rows in, same as this route's old fixed limit=200.
      query.set("limit", "200");
      const result = await adminFetch(`/api/admin/audit-log?${query.toString()}`);
      return unwrapAdminResult<{ entries: AuditEntry[] }>(result).entries;
    },
  });

  return {
    entries: entries ?? null,
    error: queryError ? (queryError as Error).message : null,
  };
}
