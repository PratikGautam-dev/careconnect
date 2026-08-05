"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { getAdminSecret, setAdminSecret } from "@/lib/adminAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/** Gates any platform-admin page behind TENANTS_ADMIN_SECRET -- re-verified
 * against the backend on submit (never just "trust a non-empty field"), same
 * as every other shared-secret gate in this project. Wrap a whole page's
 * content in this; children only render once unlocked. */
export function AdminSecretGate({ title, children }: { title: string; children: React.ReactNode }) {
  const [status, setStatus] = useState<"checking" | "gate" | "unlocked">("checking");
  const [secretInput, setSecretInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setStatus(getAdminSecret() ? "unlocked" : "gate");
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/tenants/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret: secretInput }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Incorrect admin secret.");
        return;
      }
      setAdminSecret(secretInput);
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
      <div className="flex min-h-screen items-center justify-center bg-paper px-space-4">
        <Card className="w-full max-w-sm p-space-6">
          <div className="mb-space-5 flex items-center gap-space-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-brand-600 font-display text-[16px] font-extrabold text-white">
              H
            </div>
            <div>
              <span className="block text-eyebrow">DAAP</span>
              <span className="block text-[16px] font-bold text-ink-900">CareConnect</span>
            </div>
          </div>
          <h1 className="text-display mb-space-1 !text-[22px]">{title}</h1>
          <p className="text-body mb-space-5">This page shows tenant credentials, so it&apos;s gated separately from onboarding.</p>
          <form onSubmit={handleSubmit}>
            <Field label="Admin secret" htmlFor="admin_secret" error={error || undefined}>
              <Input
                id="admin_secret"
                type="password"
                autoFocus
                value={secretInput}
                invalid={!!error}
                onChange={(e) => setSecretInput(e.target.value)}
              />
            </Field>
            <Button type="submit" disabled={submitting || !secretInput} className="mt-space-2 w-full" size="lg">
              {submitting ? "Checking…" : "Continue"}
            </Button>
          </form>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
}
