"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { GoogleIcon } from "@/components/ui/GoogleIcon";
import { Input } from "@/components/ui/Input";
import { saveStaffSession } from "@/lib/staffAuth";
import { googleLoginUrl } from "@/lib/userAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function PortalLoginPage() {
  const router = useRouter();

  const [staffEmail, setStaffEmail] = useState("");
  const [staffPassword, setStaffPassword] = useState("");
  const [staffError, setStaffError] = useState<string | null>(null);
  const [staffSubmitting, setStaffSubmitting] = useState(false);

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
      const data = await res.json();
      if (!res.ok) {
        setStaffError(data.error || "Incorrect email or password.");
        return;
      }
      saveStaffSession(data.access_token, data.refresh_token, {
        id: data.staff.id,
        name: data.staff.name,
        role: data.staff.role,
        hospital: data.staff.hospital,
        permissions: data.permissions,
      });
      // A doctor gets their own dashboard, not the shared staff portal --
      // /portal/appointments and /portal/patients show every patient at the
      // hospital with no per-doctor filtering (that scoping only exists on
      // the dedicated /api/doctor/* routes), so a doctor landing there by
      // default would defeat the whole point of a per-doctor login.
      router.push(data.staff.role === "doctor" ? "/doctor/dashboard" : "/portal/dashboard");
    } catch {
      setStaffError("Couldn't reach the server. Please try again.");
    } finally {
      setStaffSubmitting(false);
    }
  }

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
        <p className="text-body mb-space-5">Sign in with your Google account or your individual staff email and password.</p>

        <a
          href={googleLoginUrl()}
          className="inline-flex h-14 w-full items-center justify-center gap-space-3 rounded-md border border-line bg-card text-[15px] font-semibold text-ink-900 shadow-[var(--shadow-sm)] transition-colors duration-150 hover:border-brand-300 hover:bg-brand-50 active:bg-brand-100"
        >
          <GoogleIcon size={20} />
          Continue with Google
        </a>

        <div className="my-space-5 flex items-center gap-space-3 text-[12px] font-medium uppercase text-ink-400">
          <span className="h-px flex-1 bg-line" />
          or
          <span className="h-px flex-1 bg-line" />
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
          <Field label="Password" htmlFor="staff_password" error={staffError || undefined}>
            <Input
              id="staff_password"
              type="password"
              value={staffPassword}
              invalid={!!staffError}
              onChange={(e) => setStaffPassword(e.target.value)}
            />
          </Field>
          <Button
            type="submit"
            disabled={staffSubmitting || !staffEmail || !staffPassword}
            className="mt-space-2 w-full"
            size="lg"
          >
            {staffSubmitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-space-4 text-center text-[12.5px] text-ink-400">
          Signing in as a doctor?{" "}
          <a href="/doctor/login" className="font-semibold text-brand-600 hover:underline">
            Doctor login
          </a>
        </p>

        <p className="mt-space-5 text-center text-[12.5px] text-ink-400">
          Don&apos;t have a hospital account yet?{" "}
          <a href="/auth" className="font-semibold text-brand-600 hover:underline">
            Set one up
          </a>
        </p>
      </Card>
    </div>
  );
}
