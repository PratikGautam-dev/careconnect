"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { getAdminToken, setAdminToken } from "@/lib/adminAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/** Gates any platform-admin page behind an individual super-admin account
 * (replacing the old shared TENANTS_ADMIN_SECRET) -- re-verified against the
 * backend on submit, never just "trust a non-empty field". Wrap a whole
 * page's content in this; children only render once unlocked. */
export function AdminSecretGate({ title, children }: { title: string; children: React.ReactNode }) {
  const [status, setStatus] = useState<"checking" | "gate" | "unlocked">("checking");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setStatus(getAdminToken() ? "unlocked" : "gate");
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/super/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Incorrect email or password.");
        return;
      }
      setAdminToken(data.access_token, data.super_admin);
      setStatus("unlocked");
    } catch {
      setError("Couldn't reach the server. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (status === "checking") return null;

  if (status === "gate") {
    return (
      <div className="bg-paper px-space-4 flex min-h-screen items-center justify-center">
        <Card className="p-space-6 w-full max-w-sm">
          <div className="mb-space-5 flex">
            <Image
              src="/logo-full.png"
              alt="DAAP CareConnect"
              width={1448}
              height={410}
              className="h-10 w-auto"
              priority
            />
          </div>
          <h1 className="text-display mb-space-1 !text-[22px]">{title}</h1>
          <p className="text-body mb-space-5">
            This page shows tenant credentials, so it&apos;s gated separately from onboarding.
          </p>
          <form onSubmit={handleSubmit}>
            <Field label="Email" htmlFor="super_admin_email">
              <Input
                id="super_admin_email"
                type="email"
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
            <Field label="Password" htmlFor="super_admin_password" error={error || undefined}>
              <PasswordInput
                id="super_admin_password"
                value={password}
                invalid={!!error}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <Button
              type="submit"
              disabled={submitting || !email || !password}
              className="mt-space-2 w-full"
              size="lg"
            >
              {submitting ? "Checking…" : "Continue"}
            </Button>
          </form>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
}
