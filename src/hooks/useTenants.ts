import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";
import {
  paymentSettingsQueryKey,
  tenantQueryKey,
  type PaymentSettingsDetail,
  type TenantDetail,
} from "@/hooks/useEditTenant";

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

export type TenantProfile = Pick<
  TenantDetail,
  "owners" | "enabled_features" | "feature_default_labels"
>;

/** On-demand full-detail fetch for the /admin/tenants Hospital Directory's
 * right-rail master-detail panel -- the list's own summary rows
 * (useTenants() above) intentionally carry none of this (owners/
 * enabled_features only exist on the single-tenant GET, to keep the list
 * query itself N+1-free). Shares its query key with useEditTenant.ts's own
 * fetch of the same tenant, so opening the edit page right after just
 * reads from cache instead of refetching. */
export function useTenantProfile(tenantId: number | null): TenantProfile | null {
  const { data } = useQuery({
    queryKey: tenantQueryKey(tenantId ?? -1),
    retry: false,
    enabled: tenantId != null,
    queryFn: async () => {
      const result = await adminFetch(`/api/admin/tenants/${tenantId}`);
      return unwrapAdminResult<{ tenant: TenantDetail }>(result).tenant;
    },
  });
  return data ?? null;
}

/** On-demand payment-routing fetch for the same Hospital Directory
 * right-rail panel -- own/platform Razorpay and the GST/platform-fee
 * override live on a separate endpoint from the tenant detail above
 * (admin/payment_settings_api.py), same reasoning useTenantProfile's own
 * docstring gives for keeping it off the list summary. Shares its query key
 * with useEditTenant.ts's own fetch, so opening the edit page right after
 * reads from cache instead of refetching. */
export function useTenantPaymentSettings(tenantId: number | null): PaymentSettingsDetail | null {
  const { data } = useQuery({
    queryKey: paymentSettingsQueryKey(tenantId ?? -1),
    retry: false,
    enabled: tenantId != null,
    queryFn: async () => {
      const result = await adminFetch(`/api/admin/tenants/${tenantId}/payment-settings`);
      return unwrapAdminResult<PaymentSettingsDetail>(result);
    },
  });
  return data ?? null;
}
