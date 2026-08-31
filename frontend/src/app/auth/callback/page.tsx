"use client";

import { useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Card } from "@/components/ui/Card";
import { saveStaffSession } from "@/lib/staffAuth";
import { fetchAuthMe, saveUserSession } from "@/lib/userAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

// Section 15 / migration 0018: auth/google_oauth.py's /auth/google/callback
// lands here with one of two query params, depending on whether this Google
// identity already has a staff_details row (an admin created via the
// staff-management UI, or someone who's already onboarded a hospital --
// there's no separate 'owner' role, confirmed with the user, so "hospital
// owner" and "admin" are the same thing now):
//   ?staff_refresh_token=... -- a real staff account. Exchanged here for a
//     full staff session (access token, refresh token, role, permissions)
//     via the same /api/portal/staff/refresh call any staff JWT expiry
//     uses, then straight into the dashboard -- one identity, one hospital,
//     so there's never a picker to show.
//   ?token=... -- no staff account yet. Stored as the short-lived
//     Google-identity session the onboarding wizard authenticates its
//     submission with, then routed to /admin/onboard-hospital.
function CallbackContent() {
  const router = useRouter();
  const params = useSearchParams();
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const staffRefreshToken = params.get("staff_refresh_token");
    const userToken = params.get("token");

    if (staffRefreshToken) {
      (async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/api/portal/staff/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: staffRefreshToken }),
          });
          if (!res.ok) {
            router.replace("/auth?error=google_sign_in_failed");
            return;
          }
          const data = await res.json();
          saveStaffSession(data.access_token, data.refresh_token, {
            id: data.staff.id,
            name: data.staff.name,
            role: data.staff.role,
            hospital: data.staff.hospital,
            permissions: data.permissions,
          });
          router.push("/portal/dashboard");
        } catch {
          router.replace("/auth?error=google_sign_in_failed");
        }
      })();
      return;
    }

    if (!userToken) {
      router.replace("/auth?error=google_sign_in_failed");
      return;
    }
    saveUserSession(userToken);

    (async () => {
      const me = await fetchAuthMe();
      if (!me) {
        router.replace("/auth?error=google_sign_in_failed");
        return;
      }
      router.replace("/admin/onboard-hospital");
    })();
  }, [params, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-space-4">
      <Card className="w-full max-w-sm p-space-6 text-center">
        <p className="text-body">Signing you in…</p>
      </Card>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense>
      <CallbackContent />
    </Suspense>
  );
}
