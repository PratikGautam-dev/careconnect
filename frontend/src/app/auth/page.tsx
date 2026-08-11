"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Card } from "@/components/ui/Card";
import { GoogleIcon } from "@/components/ui/GoogleIcon";
import { googleLoginUrl } from "@/lib/userAuth";

// Section 15: the single sign-in entry point for BOTH "set up your hospital"
// (landing page CTA) and "hospital login" (/portal/login's primary action)
// -- Google OAuth doesn't naturally distinguish sign-up from sign-in the way
// a password form does, so there's one button here, and /auth/callback
// decides where to send someone afterward based on how many hospitals their
// Google account already owns (0 = onboarding wizard, 1 = straight into
// that hospital, 2+ = a picker).
function AuthContent() {
  const params = useSearchParams();
  const error = params.get("error");

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-space-4">
      <Card className="w-full max-w-sm p-space-6">
        <div className="mb-space-5 flex items-end gap-space-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand-600 font-display text-[16px] font-extrabold text-white">
            H
          </div>
          <div>
            <span className="block text-eyebrow">DAAP</span>
            <span className="block text-[16px] font-bold text-ink-900">CareConnect</span>
          </div>
        </div>

        <h1 className="text-display mb-space-1 !text-[22px]">Sign in</h1>
        <p className="text-body mb-space-5">
          Continue with Google to set up a new hospital or get to a portal you already own.
        </p>

        {error && (
          <p className="mb-space-4 rounded-md bg-error-tint p-space-3 text-[13px] font-medium text-error">
            Something went wrong signing in with Google. Please try again.
          </p>
        )}

        <a
          href={googleLoginUrl()}
          className="inline-flex h-14 w-full items-center justify-center gap-space-3 rounded-md border border-line bg-card text-[15px] font-semibold text-ink-900 shadow-[var(--shadow-sm)] transition-colors duration-150 hover:border-brand-300 hover:bg-brand-50 active:bg-brand-100"
        >
          <GoogleIcon size={20} />
          Continue with Google
        </a>

        <p className="mt-space-5 text-center text-[12.5px] text-ink-400">
          Prefer a hospital password instead?{" "}
          <a href="/portal/login" className="font-semibold text-brand-600 hover:underline">
            Staff login
          </a>
        </p>
      </Card>
    </div>
  );
}

export default function AuthPage() {
  return (
    <Suspense>
      <AuthContent />
    </Suspense>
  );
}
