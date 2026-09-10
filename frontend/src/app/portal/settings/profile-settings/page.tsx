"use client";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { PortalShell } from "@/components/portal/PortalShell";
import { useStaffSession } from "@/lib/staffAuth";
import { useChangePassword } from "@/hooks/useChangePassword";
import { useStaffProfile } from "@/hooks/useStaffProfile";

/** Personal account settings -- reachable from the user dropdown in
 * PortalSidebar, not from the main nav (it's per-person, not gated by any
 * page-key permission like /portal/settings' hospital-wide settings are).
 * Own-profile details (name/email -- role/hospital are already shown
 * elsewhere in the shell, no need to repeat them here) plus the
 * change-password form; a natural place to add other self-service account
 * fields later. */
export default function ProfileSettingsPage() {
  const session = useStaffSession();
  const { profile, error: profileError } = useStaffProfile();
  const {
    currentPassword, setCurrentPassword,
    newPassword, setNewPassword,
    confirmPassword, setConfirmPassword,
    errors, submitting,
    handleSubmit,
  } = useChangePassword();

  return (
    <PortalShell hospital={session?.hospital || null} active="profile-settings">
      <PageHeader title="Profile settings" description={session ? `${session.name} — ${session.role}` : undefined} />

      <Card className="mb-space-5 max-w-md p-space-5">
        <h2 className="mb-space-3 text-[15px] font-bold text-ink-900">Your details</h2>
        {profileError ? (
          <p className="text-[13px] text-error">{profileError}</p>
        ) : !profile ? (
          <p className="text-[13px] text-ink-400">Loading…</p>
        ) : (
          <dl className="flex flex-col gap-space-3">
            <div>
              <dt className="text-[11px] font-semibold text-ink-400 uppercase">Name</dt>
              <dd className="text-[14px] text-ink-900">{profile.name}</dd>
            </div>
            <div>
              <dt className="text-[11px] font-semibold text-ink-400 uppercase">Email</dt>
              <dd className="text-[14px] text-ink-900">{profile.email}</dd>
            </div>
          </dl>
        )}
      </Card>

      <Card className="max-w-md p-space-5">
        <h2 className="mb-space-3 text-[15px] font-bold text-ink-900">Change password</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-space-3">
          <Field label="Current password" htmlFor="current_password" required>
            <PasswordInput
              id="current_password"
              autoComplete="current-password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
          </Field>
          <Field label="New password" htmlFor="new_password" required hint="At least 8 characters.">
            <PasswordInput
              id="new_password"
              autoComplete="new-password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </Field>
          <Field label="Confirm new password" htmlFor="confirm_password" required>
            <PasswordInput
              id="confirm_password"
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </Field>

          {errors.length > 0 && (
            <div className="rounded-md border border-error bg-error-tint p-space-3 text-[12.5px] text-error">
              <ul className="list-disc pl-space-4">
                {errors.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
          )}

          <Button type="submit" disabled={submitting} className="mt-space-1 self-start">
            {submitting ? "Saving…" : "Change password"}
          </Button>
        </form>
      </Card>
    </PortalShell>
  );
}
