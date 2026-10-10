"use client";

import { useState } from "react";
import { IdCard, Mail, Pencil, UserRound } from "lucide-react";
import { AccountDetailRow } from "@/components/account/AccountDetailRow";
import { ChangePasswordCard } from "@/components/account/ChangePasswordCard";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { useAdminChangePassword, useAdminProfile } from "@/hooks/useAdminProfile";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
}

/** /admin/profile -- the super admin's own account page, same two-card
 * layout as the staff portal's Profile page (shared account components):
 * a profile card (here EDITABLE -- name and email) and Change Password.
 * Changing the email asks for the current password. */
export default function AdminProfilePage() {
  const { profile, error, saveProfile, saving } = useAdminProfile();
  const changePassword = useAdminChangePassword();

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  function startEditing() {
    if (!profile) return;
    setName(profile.name);
    setEmail(profile.email);
    setCurrentPassword("");
    setFormError(null);
    setEditing(true);
  }

  const emailChanged = !!profile && email.trim() !== profile.email;

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    const message = await saveProfile({ name: name.trim(), email: email.trim(), currentPassword });
    if (message) setFormError(message);
    else setEditing(false);
  }

  return (
    <>
      <PageHeader
        title="Profile"
        description={profile ? `${profile.name} — Super admin` : undefined}
      />

      {error ? (
        <p className="text-error text-[13px]">{error}</p>
      ) : !profile ? (
        <p className="text-ink-400 text-[13px]">Loading…</p>
      ) : (
        <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-2">
          <Card className="p-space-4">
            <div className="gap-space-3 flex flex-wrap items-start justify-between">
              <div className="gap-space-3 flex items-center">
                <span className="bg-brand-100 text-brand-700 flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-[18px] font-bold">
                  {initials(profile.name)}
                </span>
                <div>
                  <p className="text-ink-900 text-[15px] font-bold">{profile.name}</p>
                  <p className="text-ink-600 text-[12.5px]">Super admin</p>
                </div>
              </div>
              {!editing && (
                <Button type="button" variant="secondary" onClick={startEditing}>
                  <Pencil size={13} /> Edit Profile
                </Button>
              )}
            </div>

            {editing ? (
              <form onSubmit={handleSave} className="mt-space-4 gap-space-3 flex flex-col">
                <Field label="Name" htmlFor="admin_name" required>
                  <Input
                    id="admin_name"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </Field>
                <Field
                  label="Email"
                  htmlFor="admin_email"
                  required
                  hint="This is the email you sign in with."
                >
                  <Input
                    id="admin_email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </Field>
                {emailChanged && (
                  <Field
                    label="Current password"
                    htmlFor="admin_email_password"
                    required
                    hint="Needed to change your sign-in email."
                  >
                    <PasswordInput
                      id="admin_email_password"
                      autoComplete="current-password"
                      required
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                    />
                  </Field>
                )}
                {formError && <p className="text-error text-[12.5px] font-medium">{formError}</p>}
                <div className="gap-space-2 flex">
                  <Button type="submit" disabled={saving || !name.trim() || !email.trim()}>
                    {saving ? "Saving…" : "Save changes"}
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setEditing(false)}>
                    Cancel
                  </Button>
                </div>
              </form>
            ) : (
              <div className="mt-space-4 space-y-space-2 border-line pt-space-3 border-t">
                <AccountDetailRow icon={UserRound} label="Name" value={profile.name} />
                <AccountDetailRow icon={Mail} label="Email" value={profile.email} />
                <AccountDetailRow icon={IdCard} label="Role" value="Super admin" />
              </div>
            )}
          </Card>

          <ChangePasswordCard form={changePassword} />
        </div>
      )}
    </>
  );
}
