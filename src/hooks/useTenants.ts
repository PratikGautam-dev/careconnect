import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";

export type Tenant = {
  id: number;
  name: string;
  whatsapp_phone_number_id: string;
  data_tier: string;
  is_active: boolean;
  // Settings -> General's "Contact Information" address field -- the
  // closest real thing to a directory "location" column, free-text/optional.
  contact_address: string | null;
  // Raw HospitalRow.created_at (db.get_hospital_created_at_map()) -- null
  // only for a malformed/legacy row, never for an ordinary one.
  created_at: string | null;
  tenant_type: string;
  // True once an operator has ever saved an explicit admin_capabilities
  // list for this tenant (Access Control page) -- false means it's still
  // following its tenant_type default (portal/capabilities.py).
  has_custom_capabilities: boolean;
};

export type StalledSignup = { id: number; email: string; name: string | null; created_at: string };

/** Loads the /admin/tenants overview's two lists: every tenant, and every
 * Google account that signed in but never finished onboarding. The
 * stalled-signups fetch is best-effort -- its own failure doesn't blank the
 * (more important) tenants list, so it's a second, independent query rather
 * than bundled into the first's queryFn. */
export function useTenants() {
  const {
    data: tenants,
    error: tenantsError,
    refetch,
  } = useQuery({
    queryKey: ["admin-tenants"],
    retry: false,
    queryFn: async () => {
      const result = await adminFetch("/api/admin/tenants");
      return unwrapAdminResult<{ tenants: Tenant[] }>(result).tenants;
    },
  });

  const { data: stalledSignups } = useQuery({
    queryKey: ["admin-stalled-signups"],
    retry: false,
    queryFn: async () => {
      const result = await adminFetch("/api/admin/stalled-signups");
      return unwrapAdminResult<{ users: StalledSignup[] }>(result).users;
    },
  });

  return {
    tenants: tenants ?? null,
    stalledSignups: stalledSignups ?? null,
    error: tenantsError ? (tenantsError as Error).message : null,
    load: refetch,
  };
}
