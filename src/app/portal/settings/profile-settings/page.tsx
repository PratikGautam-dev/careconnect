"use client";

import { useState } from "react";
import { IdCard, Mail, MapPin, Pencil, Phone } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { AccountDetailRow } from "@/components/account/AccountDetailRow";
import { ChangePasswordCard } from "@/components/account/ChangePasswordCard";
import { EditProfileDialog } from "@/components/portal/EditProfileDialog";
import { PortalShell } from "@/components/portal/PortalShell";
import { useStaffSession } from "@/lib/staffAuth";
import { useChangePassword } from "@/hooks/useChangePassword";
import { useStaffProfile } from "@/hooks/useStaffProfile";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
}

/** Personal account page -- reachable from the sidebar's own "Profile" nav
 * entry and the account dropdown alike (PortalSidebar.tsx). Just two cards:
 * Profile (useStaffProfile -> GET /api/portal/staff/me ->
 * db.get_own_profile()) showing only fields with a real backing column, and
 * Change Password. "Edit Profile" lets a staff member change their own
 * name (PUT /api/portal/staff/me) -- every other field here stays
 * admin-managed via the Staff page's own edit dialog. */
export default function ProfileSettingsPage() {
  const session = useStaffSession();
  const { profile, error: profileError } = useStaffProfile();
  const changePassword = useChangePassword();
  const [editOpen, setEditOpen] = useState(false);

  return (
    <PortalShell hospital={session?.hospital || null} active="profile-settings">
      <PageHeader
        title="Profile"
        description={session ? `${session.name} — ${session.role_name}` : undefined}
      />

      {profileError ? (
        <p className="text-error text-[13px]">{profileError}</p>
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
                  <p className="text-ink-600 text-[12.5px]">{profile.role_name}</p>
                  {(profile.is_doctor_role ? profile.specialization : profile.department_name) && (
                    <Badge tone="brand" className="mt-space-1 tracking-normal normal-case">
                      {profile.is_doctor_role ? profile.specialization : profile.department_name}
                    </Badge>
                  )}
                </div>
              </div>
              <Button type="button" variant="secondary" onClick={() => setEditOpen(true)}>
                <Pencil size={13} /> Edit Profile
              </Button>
            </div>

            <div className="mt-space-4 space-y-space-2 border-line pt-space-3 border-t">
              <AccountDetailRow icon={IdCard} label="Staff ID" value={profile.employee_id || "—"} />
              <AccountDetailRow icon={Mail} label="Email" value={profile.email} />
              <AccountDetailRow icon={Phone} label="Phone" value={profile.phone || "—"} />
              <AccountDetailRow icon={MapPin} label="Address" value={profile.address || "—"} />
            </div>
          </Card>

          <ChangePasswordCard form={changePassword} />
        </div>
      )}

      {profile && (
        <EditProfileDialog
          open={editOpen}
          onOpenChange={setEditOpen}
          currentName={profile.name}
        />
      )}
    </PortalShell>
  );
}
