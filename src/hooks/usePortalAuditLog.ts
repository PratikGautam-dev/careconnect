import { useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";

export type AuditEntry = {
  id: number;
  actor_level: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  before_value: Record<string, unknown> | null;
  after_value: Record<string, unknown> | null;
  created_at: string;
};

/** Loads this hospital's own (capability-gated) activity log. */
export function usePortalAuditLog(ready: boolean) {
  // undefined = not loaded yet, null = this tenant lacks manage_settings (the
  // capability that also gates the settings-update route) so the page shows
  // an unavailable message rather than an error.
  const { data: entries } = useQuery({
    queryKey: ["portal-audit-log"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/audit-log");
      if (!result.ok) return null;
      return (result.data as { entries: AuditEntry[] }).entries;
    },
  });

  return { entries };
}
