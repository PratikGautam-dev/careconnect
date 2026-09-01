import { useCallback, useEffect, useState } from "react";
import { adminFetch } from "@/lib/adminAuth";

export type Tenant = {
  id: number;
  name: string;
  whatsapp_phone_number_id: string;
  data_tier: string;
  is_active: boolean;
};

export type StalledSignup = { id: number; email: string; name: string | null; created_at: string };

/** Loads the /admin/tenants overview's two lists: every tenant, and every
 * Google account that signed in but never finished onboarding. */
export function useTenants() {
  const [tenants, setTenants] = useState<Tenant[] | null>(null);
  const [stalledSignups, setStalledSignups] = useState<StalledSignup[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await adminFetch("/api/admin/tenants");
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — refresh to sign in again." : result.error);
      return;
    }
    setTenants((result.data as { tenants: Tenant[] }).tenants);

    // Item 5 (Spec.md Section 0): who's signed in with Google but never
    // finished onboarding -- a separate, non-fatal fetch, since the main
    // tenants list is the more important thing on this page to get right.
    const signupsResult = await adminFetch("/api/admin/stalled-signups");
    if (signupsResult.ok) {
      setStalledSignups((signupsResult.data as { users: StalledSignup[] }).users);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { tenants, stalledSignups, error };
}
