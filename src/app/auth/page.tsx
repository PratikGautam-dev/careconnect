"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Card } from "@/components/ui/Card";
import { GoogleIcon } from "@/components/ui/GoogleIcon";
import { googleLoginUrl } from "@/lib/userAuth";

// Single sign-in entry point for both "set up your hospital" and "hospital
// login" -- Google OAuth doesn't distinguish sign-up from sign-in, so
// /auth/callback decides where to send someone based on how many
// hospitals their Google account already owns (0 = onboarding wizard, 1 =
// straight into that hospital, 2+ = a picker).
function AuthContent() {
  const params = useSearchParams();
  const error = params.get("error");

  return (
    <div className="bg-paper px-space-4 flex min-h-screen items-center justify-center">
      <Card className="p-space-6 w-full max-w-sm">
        <div className="mb-space-5 gap-space-3 flex items-end">
          <div className="bg-brand-600 font-display flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-[16px] font-extrabold text-white">
            H
          </div>
          <div>
            <span className="text-eyebrow block">DAAP</span>
            <span className="text-ink-900 block text-[16px] font-bold">CareConnect</span>
          </div>
        </div>

        <h1 className="text-display mb-space-1 !text-[22px]">Sign in</h1>
        <p className="text-body mb-space-5">
          Continue with Google to set up a new hospital or get to a portal you already own.
        </p>

        {error && (
          <p className="mb-space-4 bg-error-tint p-space-3 text-error rounded-md text-[13px] font-medium">
            Something went wrong signing in with Google. Please try again.
          </p>
        )}

        <a
          href={googleLoginUrl()}
          className="gap-space-3 border-line bg-card text-ink-900 hover:border-brand-300 hover:bg-brand-50 active:bg-brand-100 inline-flex h-14 w-full items-center justify-center rounded-md border text-[15px] font-semibold shadow-[var(--shadow-sm)] transition-colors duration-150"
        >
          <GoogleIcon size={20} />
          Continue with Google
        </a>

        <p className="mt-space-5 text-ink-400 text-center text-[12.5px]">
          Prefer a hospital password instead?{" "}
          <a href="/portal/login" className="text-brand-600 font-semibold hover:underline">
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
