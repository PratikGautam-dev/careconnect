"use client";

import { useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Card } from "@/components/ui/Card";
import { setStaffAccessToken } from "@/lib/staffAuth";
import { fetchAuthMe, saveUserSession } from "@/lib/userAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

// auth/google_oauth.py's /auth/google/callback lands here with one of two
// signals, depending on whether this Google identity already has a
// staff_details row:
//   ?staff=1 -- a real staff account. The backend already set the refresh
//     token as an httpOnly cookie on the redirect that landed here (never
//     in this URL), so this is just a routing flag -- exchange it for an
//     access token + full session via /api/portal/staff/refresh (cookie
//     sent automatically), then straight into the dashboard.
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

    const isStaffLogin = params.get("staff") === "1";
    const userToken = params.get("token");

    if (isStaffLogin) {
      (async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/api/portal/staff/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
            credentials: "include",
          });
          if (!res.ok) {
            router.replace("/auth?error=google_sign_in_failed");
            return;
          }
          const data = await res.json();
          setStaffAccessToken(data.access_token);
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
    <div className="bg-paper px-space-4 flex min-h-screen items-center justify-center">
      <Card className="p-space-6 w-full max-w-sm text-center">
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
