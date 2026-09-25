import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";

// Matches GET /api/admin/tenants/{id}/audit-log (admin/tenants_api.py) --
// every audit_logs row for one tenant, both actor levels. Access
// Control/Feature Toggles' "Recent Access/Feature Changes" panels reuse this
// as-is rather than filtering to just admin_capabilities/enabled_features --
// update_tenant() (admin/tenants_api.py) already writes ONE "tenant.update"
// entry per save covering every changed field, so there's nothing narrower
// to filter down to.
export type TenantAuditEntry = {
  id: number;
  actor_level: string;
  actor_label: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  before_value: Record<string, unknown> | null;
  after_value: Record<string, unknown> | null;
  created_at: string;
};

export function useTenantAuditLog(tenantId: number | null) {
  const { data, error, refetch } = useQuery({
    queryKey: ["admin-tenant-audit-log", tenantId],
    enabled: tenantId !== null,
    retry: false,
    queryFn: async () => {
      const result = await adminFetch(`/api/admin/tenants/${tenantId}/audit-log`);
      return unwrapAdminResult<{ entries: TenantAuditEntry[] }>(result).entries;
    },
  });

  return {
    entries: data ?? null,
    error: error ? (error as Error).message : null,
    load: refetch,
  };
}
