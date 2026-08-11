"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { savePortalSession } from "@/lib/portalAuth";
import {
  fetchAuthMe,
  saveUserSession,
  selectHospital,
  type OwnedHospital,
} from "@/lib/userAuth";

// Section 15: user_auth.py's /auth/google/callback lands here with
// ?token=<user session token> after Google sign-in completes. This page's
// only job is to store that token, ask /api/auth/me how many hospitals the
// signed-in account owns, and route accordingly -- 0 means a brand new
// account (onboarding wizard), 1 means go straight in (issuing the
// existing hospital-scoped portal token via selectHospital()), and 2+ means
// show the picker below.
function CallbackContent() {
  const router = useRouter();
  const params = useSearchParams();
  const [hospitals, setHospitals] = useState<OwnedHospital[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [entering, setEntering] = useState(false);
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const token = params.get("token");
    if (!token) {
      router.replace("/auth?error=google_sign_in_failed");
      return;
    }
    saveUserSession(token);

    (async () => {
      const me = await fetchAuthMe();
      if (!me) {
        router.replace("/auth?error=google_sign_in_failed");
        return;
      }
      if (me.owned_hospitals.length === 0) {
        router.replace("/admin/onboard-hospital");
        return;
      }
      if (me.owned_hospitals.length === 1) {
        await enterHospital(me.owned_hospitals[0].id);
        return;
      }
      setHospitals(me.owned_hospitals);
    })();
  }, [params, router]);

  async function enterHospital(hospitalId: number) {
    setEntering(true);
    const result = await selectHospital(hospitalId);
    if (!result) {
      setError("Couldn't open that hospital's portal. Please try again.");
      setEntering(false);
      return;
    }
    savePortalSession(result.token, result.hospital);
    router.push("/portal/dashboard");
  }

  if (hospitals) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper px-space-4">
        <Card className="w-full max-w-sm p-space-6">
          <h1 className="text-display mb-space-1 !text-[22px]">Choose a hospital</h1>
          <p className="text-body mb-space-5">Your Google account manages more than one hospital.</p>
          <div className="flex flex-col gap-space-2">
            {hospitals.map((h) => (
              <Button
                key={h.id}
                variant="secondary"
                size="lg"
                disabled={entering}
                className="w-full justify-start"
                onClick={() => enterHospital(h.id)}
              >
                {h.name}
              </Button>
            ))}
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-space-4">
      <Card className="w-full max-w-sm p-space-6 text-center">
        {error ? (
          <>
            <p className="mb-space-4 text-[14px] font-medium text-error">{error}</p>
            <Button href="/auth" size="lg" className="w-full">
              Try again
            </Button>
          </>
        ) : (
          <p className="text-body">Signing you in…</p>
        )}
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
