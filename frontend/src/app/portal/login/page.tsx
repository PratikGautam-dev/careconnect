"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { savePortalSession } from "@/lib/portalAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function PortalLoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showForgotHelp, setShowForgotHelp] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/portal/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Incorrect password.");
        return;
      }
      savePortalSession(data.token, data.hospital);
      router.push("/portal/dashboard");
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

        <h1 className="text-display mb-space-1 !text-[22px]">Staff login</h1>
        <p className="text-body mb-space-5">Enter your hospital&apos;s bookings portal password.</p>

        <form onSubmit={handleSubmit}>
          <Field label="Password" htmlFor="password" error={error || undefined}>
            <Input
              id="password"
              type="password"
              autoFocus
              value={password}
              invalid={!!error}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <Button type="submit" disabled={submitting || !password} className="mt-space-2 w-full" size="lg">
            {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-space-3 text-center text-[12.5px]">
          <button
            type="button"
            onClick={() => setShowForgotHelp((v) => !v)}
            className="font-semibold text-brand-600 hover:underline"
          >
            Forgot password?
          </button>
        </p>
        {showForgotHelp && (
          <p className="mt-space-2 rounded-md bg-paper p-space-3 text-center text-[12.5px] text-ink-600">
            Portal passwords are reset by your platform administrator, not self-service. Contact them to have it
            changed.
          </p>
        )}

        <p className="mt-space-5 text-center text-[12.5px] text-ink-400">
          Don&apos;t have a hospital account yet?{" "}
          <a href="/admin/onboard-hospital" className="font-semibold text-brand-600 hover:underline">
            Set one up
          </a>
        </p>
      </Card>
    </div>
  );
}
