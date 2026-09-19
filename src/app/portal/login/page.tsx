"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { GoogleIcon } from "@/components/ui/GoogleIcon";
import { Input } from "@/components/ui/Input";
import {
  saveStaffTokens,
  staffSessionFromAuthResponse,
  useSetStaffSession,
  type StaffAuthResponse,
} from "@/lib/staffAuth";
import { googleLoginUrl } from "@/lib/userAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function PortalLoginPage() {
  const router = useRouter();
  const setStaffSession = useSetStaffSession();

  const [staffEmail, setStaffEmail] = useState("");
  const [staffPassword, setStaffPassword] = useState("");
  const [staffError, setStaffError] = useState<string | null>(null);
  const [staffSubmitting, setStaffSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function handleStaffSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStaffSubmitting(true);
    setStaffError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/portal/staff/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: staffEmail, password: staffPassword }),
      });
      const data: StaffAuthResponse & { error?: string } = await res.json();
      if (!res.ok) {
        setStaffError(data.error || "Couldn't sign in. Please try again.");
        return;
      }
      saveStaffTokens(data.access_token, data.refresh_token);
      // Seed StaffSessionContext straight from this response instead of
      // letting the dashboard render ungated for a moment and then pop into
      // its real per-role state once a separate /me fetch resolves -- the
      // login response already carries the exact same staff+permissions
      // shape /me does (see staffSessionFromAuthResponse's own docstring),
      // so there's nothing to wait on.
      setStaffSession(staffSessionFromAuthResponse(data));
      // Every role (including doctor) lands in the same shared portal now --
      // what they see there is driven by the RBAC permission matrix, not by
      // which door they logged in through.
      router.push("/portal/dashboard");
    } catch {
      setStaffError("Couldn't reach the server. Please try again.");
    } finally {
      setStaffSubmitting(false);
    }
  }

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
          Sign in with your Google account or your individual staff email and password.
        </p>

        <a
          href={googleLoginUrl()}
          className="gap-space-3 border-line bg-card text-ink-900 hover:border-brand-300 hover:bg-brand-50 active:bg-brand-100 inline-flex h-14 w-full items-center justify-center rounded-md border text-[15px] font-semibold shadow-[var(--shadow-sm)] transition-colors duration-150"
        >
          <GoogleIcon size={20} />
          Continue with Google
        </a>

        <div className="my-space-5 gap-space-3 text-ink-400 flex items-center text-[12px] font-medium uppercase">
          <span className="bg-line h-px flex-1" />
          or
          <span className="bg-line h-px flex-1" />
        </div>

        <form onSubmit={handleStaffSubmit}>
          <Field label="Email" htmlFor="staff_email">
            <Input
              id="staff_email"
              type="email"
              autoFocus
              value={staffEmail}
              onChange={(e) => setStaffEmail(e.target.value)}
            />
          </Field>
          <Field label="Password" htmlFor="staff_password">
            <div className="relative">
              <Input
                id="staff_password"
                type={showPassword ? "text" : "password"}
                value={staffPassword}
                invalid={!!staffError}
                onChange={(e) => setStaffPassword(e.target.value)}
                className="pr-space-9"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                tabIndex={-1}
                className="right-space-3 text-ink-400 hover:text-ink-700 absolute top-1/2 -translate-y-1/2"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </Field>
          {staffError && (
            <p className="-mt-space-2 mb-space-4 border-error bg-error-tint p-space-3 text-error rounded-md border text-[12.5px] font-medium">
              {staffError}
            </p>
          )}
          <Button
            type="submit"
            disabled={staffSubmitting || !staffEmail || !staffPassword}
            className="mt-space-2 w-full"
            size="lg"
          >
            {staffSubmitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-space-5 text-ink-400 text-center text-[12.5px]">
          Don&apos;t have a hospital account yet?{" "}
          <a href="/auth" className="text-brand-600 font-semibold hover:underline">
            Set one up
          </a>
        </p>
      </Card>
    </div>
  );
}
