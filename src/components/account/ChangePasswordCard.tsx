"use client";

import { KeyRound } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { AccountCardHeading } from "./AccountCardHeading";

/** What a change-password hook hands the card (useChangePassword for the
 * staff portal, useAdminChangePassword for the super admin) -- the card
 * itself is purely presentational, so both sides share one design. */
export type ChangePasswordFormState = {
  currentPassword: string;
  setCurrentPassword: (v: string) => void;
  newPassword: string;
  setNewPassword: (v: string) => void;
  confirmPassword: string;
  setConfirmPassword: (v: string) => void;
  errors: string[];
  submitting: boolean;
  handleSubmit: (e: React.FormEvent) => void;
};

export function ChangePasswordCard({ form }: { form: ChangePasswordFormState }) {
  return (
    <Card className="p-space-4">
      <AccountCardHeading icon={KeyRound} title="Change Password" />
      <form onSubmit={form.handleSubmit} className="gap-space-3 flex flex-col">
        <Field label="Current password" htmlFor="current_password" required>
          <PasswordInput
            id="current_password"
            autoComplete="current-password"
            required
            value={form.currentPassword}
            onChange={(e) => form.setCurrentPassword(e.target.value)}
          />
        </Field>
        <Field label="New password" htmlFor="new_password" required hint="At least 8 characters.">
          <PasswordInput
            id="new_password"
            autoComplete="new-password"
            required
            value={form.newPassword}
            onChange={(e) => form.setNewPassword(e.target.value)}
          />
        </Field>
        <Field label="Confirm new password" htmlFor="confirm_password" required>
          <PasswordInput
            id="confirm_password"
            autoComplete="new-password"
            required
            value={form.confirmPassword}
            onChange={(e) => form.setConfirmPassword(e.target.value)}
          />
        </Field>
        {form.errors.length > 0 && (
          <div className="border-error bg-error-tint p-space-3 text-error rounded-md border text-[12.5px]">
            <ul className="pl-space-4 list-disc">
              {form.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </div>
        )}
        <Button type="submit" disabled={form.submitting} className="self-start">
          {form.submitting ? "Saving…" : "Change password"}
        </Button>
      </form>
    </Card>
  );
}
