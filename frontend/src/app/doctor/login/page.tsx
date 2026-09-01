"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { saveStaffSession } from "@/lib/staffAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/** Goes through the SAME unified /api/portal/staff/login every staff role
 * uses now (docs/rbac-redis-plan.md) -- this page is just a dedicated door
 * for doctors, not a separate auth mechanism. The old standalone
 * /api/doctor/login (auth/doctor_session.py) is a different, still-live
 * token type portal/deps.py's _require_doctor() falls back to for any
 * doctor not yet migrated onto a staff_users row -- new logins should
 * always go through the unified path, so this page never calls it. */
export default function DoctorLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/portal/staff/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Invalid email or password.");
        return;
      }
      // This door is for doctors -- a non-doctor staff member (admin/
      // receptionist) with valid credentials still authenticates
      // successfully against the shared endpoint, but belongs on the
      // shared staff portal, not here. Sent there instead of left on a
      // doctor dashboard that would just 401 against every /api/doctor/*
      // call for them.
      if (data.staff.role !== "doctor") {
        router.push("/portal/dashboard");
        return;
      }
      saveStaffSession(data.access_token, data.refresh_token, {
        id: data.staff.id,
        name: data.staff.name,
        role: data.staff.role,
        hospital: data.staff.hospital,
        permissions: data.permissions,
      });
      router.push("/doctor/dashboard");
    } catch {
      setError("Couldn't reach the server. Please try again.");
    } finally {
      setSubmitting(false);
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

        <h1 className="text-display mb-space-1 !text-[22px]">Doctor login</h1>
        <p className="text-body mb-space-5">
          Sign in with the email and password your hospital administrator gave you.
        </p>

        <form onSubmit={handleSubmit}>
          <Field label="Email" htmlFor="email">
            <Input
              id="email"
              type="email"
              autoFocus
              autoComplete="username"
              value={email}
              invalid={!!error}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
          <Field label="Password" htmlFor="password" error={error || undefined}>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              invalid={!!error}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <Button type="submit" disabled={submitting || !email || !password} className="mt-space-2 w-full" size="lg">
            {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-space-4 text-center text-[12.5px] text-ink-400">
          Not a doctor?{" "}
          <a href="/portal/login" className="font-semibold text-brand-600 hover:underline">
            Staff login
          </a>
        </p>

        <p className="mt-space-5 text-center text-[12.5px] text-ink-400">
          Don&apos;t have login details yet? Ask your hospital administrator to set them up from the staff portal.
        </p>
      </Card>
    </div>
  );
}
