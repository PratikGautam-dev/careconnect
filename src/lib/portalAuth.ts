// getPortalToken/portalFetch/clearPortalSession delegate to the staff
// session in staffAuth.ts, so callers don't need their own token handling.
import { clearStaffSession, getStaffAccessToken, staffFetch } from "@/lib/staffAuth";

export type PortalHospital = {
  id: number;
  name: string;
  data_tier: string;
  enabled_features: string[];
  tenant_type: string;
  admin_capabilities: string[];
};

export function getPortalToken(): string | null {
  return getStaffAccessToken();
}

export function clearPortalSession(): Promise<void> {
  return clearStaffSession();
}

// Same FetchResult shape staffFetch already returns -- a straight
// delegation, not a reimplementation, so callers also pick up staffFetch's
// silent-refresh-on-401 behavior (an improvement over this file's old bare
// "401 -> logout", not a regression).
export const portalFetch = staffFetch;
