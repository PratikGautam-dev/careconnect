// Compatibility layer over staffAuth.ts (docs/rbac-redis-plan.md) -- every
// portal page/component below was written against this file's original
// shared-hospital-password session (portal_token/portal_hospital in
// localStorage). Rather than touching every one of those call sites,
// getPortalToken/getPortalHospital/portalFetch/clearPortalSession now just
// delegate to the staff session (staffAuth.ts) underneath -- same
// "preserve the interface, change what's underneath" discipline the
// backend's db/repositories/*.py already applies throughout this rework.
// This is what makes staff login (and Google sign-in, since
// auth/google_oauth.py's callback issues a staff session too) actually
// take effect on dashboard/appointments/messages/settings/doctors/etc.,
// which all guard themselves via usePortalGuard() -> getPortalToken() ->
// here.
import {
  clearStaffSession,
  getStaffAccessToken,
  getStaffSession,
  staffFetch,
} from "@/lib/staffAuth";

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

export function getPortalHospital(): PortalHospital | null {
  return getStaffSession()?.hospital ?? null;
}

export function clearPortalSession() {
  clearStaffSession();
}

// Same FetchResult shape staffFetch already returns -- a straight
// delegation, not a reimplementation, so callers also pick up staffFetch's
// silent-refresh-on-401 behavior (an improvement over this file's old bare
// "401 -> logout", not a regression).
export const portalFetch = staffFetch;
