"use client";

import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  Briefcase,
  Building2,
  CalendarClock,
  IdCard,
  KeyRound,
  Laptop2,
  Mail,
  MapPin,
  Pencil,
  Phone,
  User,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { PortalShell } from "@/components/portal/PortalShell";
import { useStaffSession } from "@/lib/staffAuth";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/formatDate";
import { formatWorkingDays, formatWorkingHours } from "@/lib/formatSchedule";
import { useChangePassword } from "@/hooks/useChangePassword";
import { useStaffProfile } from "@/hooks/useStaffProfile";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
}

function DetailRow({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="gap-space-3 flex items-center justify-between text-[13px]">
      <span className="gap-space-2 text-ink-400 flex items-center">
        <Icon size={14} className="shrink-0" /> {label}
      </span>
      <span className="text-ink-900 truncate text-right font-medium">{value}</span>
    </div>
  );
}

function CardHeading({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div className="mb-space-3 gap-space-2 flex items-center">
      <span className="bg-brand-50 text-brand-600 flex h-8 w-8 shrink-0 items-center justify-center rounded-md">
        <Icon size={15} />
      </span>
      <h3 className="text-ink-900 text-[13.5px] font-bold">{title}</h3>
    </div>
  );
}

/** Personal account page -- reachable from the sidebar's own "Profile" nav
 * entry and the account dropdown alike (PortalSidebar.tsx). Rebuilt from a
 * reference screenshot of a richer doctor-facing profile page (the same
 * shared PortalShell chrome as every other page here, not that mockup's own
 * different sidebar/topbar -- see this feature's plan for that call).
 * Real data everywhere the schema has it (useStaffProfile -> GET
 * /api/portal/staff/me -> db.get_own_profile(), which sources a doctor
 * login's profile from its linked doctors row); fields with no backing
 * column anywhere (alternate phone, date of birth, gender, about me,
 * employment type) render as "—" rather than invented, same convention
 * DoctorDetailPanel/StaffDetailPanel already use for missing optional
 * fields. Edit Profile has no self-service editing flow yet, so it's
 * disabled with a "Coming soon" title, same convention as every other
 * not-yet-built action elsewhere in the portal. */
export default function ProfileSettingsPage() {
  const session = useStaffSession();
  const { profile, error: profileError } = useStaffProfile();
  const {
    currentPassword,
    setCurrentPassword,
    newPassword,
    setNewPassword,
    confirmPassword,
    setConfirmPassword,
    errors,
    submitting,
    handleSubmit,
  } = useChangePassword();

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
        <div className="gap-space-4 flex flex-col">
          <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-3">
            <Card className="p-space-4 lg:col-span-2">
              <div className="gap-space-3 flex flex-wrap items-start justify-between">
                <div className="gap-space-3 flex items-center">
                  <span className="bg-brand-100 text-brand-700 flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-[18px] font-bold">
                    {initials(profile.name)}
                  </span>
                  <div>
                    <p className="text-ink-900 text-[15px] font-bold">
                      {profile.is_doctor_role ? `Dr. ${profile.name}` : profile.name}
                    </p>
                    <p className="text-ink-600 text-[12.5px]">{profile.role_name}</p>
                    {(profile.is_doctor_role
                      ? profile.specialization
                      : profile.department_name) && (
                      <Badge tone="brand" className="mt-space-1 tracking-normal normal-case">
                        {profile.is_doctor_role ? profile.specialization : profile.department_name}
                      </Badge>
                    )}
                  </div>
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  disabled
                  title="Coming soon — self-service profile editing isn't built yet"
                >
                  <Pencil size={13} /> Edit Profile
                </Button>
              </div>

              <div className="mt-space-4 space-y-space-2 border-line pt-space-3 border-t">
                <DetailRow icon={IdCard} label="Staff ID" value={profile.employee_id || "—"} />
                <DetailRow icon={Mail} label="Email" value={profile.email} />
                <DetailRow icon={Phone} label="Phone" value={profile.phone || "—"} />
                <DetailRow icon={Phone} label="Alternate Phone" value="—" />
                <DetailRow icon={User} label="Date of Birth" value="—" />
                <DetailRow icon={User} label="Gender" value="—" />
                <DetailRow icon={MapPin} label="Address" value={profile.address || "—"} />
              </div>
            </Card>

            <Card className="p-space-4">
              <CardHeading icon={Building2} title="Hospital Information" />
              <div className="space-y-space-2">
                <DetailRow icon={Building2} label="Hospital Name" value={profile.hospital.name} />
                <DetailRow
                  icon={Briefcase}
                  label="Department"
                  value={profile.department_name || "—"}
                />
                <DetailRow icon={MapPin} label="Location" value={profile.location || "—"} />
                <DetailRow
                  icon={CalendarClock}
                  label="Joining Date"
                  value={formatDate(profile.created_at)}
                />
                <DetailRow icon={Briefcase} label="Employment Type" value="—" />
              </div>
            </Card>
          </div>

          {profile.is_doctor_role && (
            <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-3">
              <div className="lg:col-span-2" />
              <Card className="p-space-4">
                <div className="mb-space-3 flex items-center justify-between">
                  <CardHeading icon={CalendarClock} title="Consultation Timings" />
                  <Link
                    href="/portal/schedule"
                    className="text-brand-600 text-[12px] font-semibold hover:underline"
                  >
                    Manage Schedule
                  </Link>
                </div>
                {profile.working_days.length === 0 ? (
                  <p className="text-ink-400 text-[12.5px]">No schedule set yet.</p>
                ) : (
                  <p className="text-ink-900 text-[13px]">
                    {formatWorkingDays(profile.working_days)}
                    {formatWorkingHours(profile.working_hours)
                      ? ` · ${formatWorkingHours(profile.working_hours)}`
                      : ""}
                  </p>
                )}
              </Card>
            </div>
          )}

          <div
            className={cn(
              "gap-space-4 grid grid-cols-1 md:grid-cols-2",
              profile.is_doctor_role && "xl:grid-cols-4",
            )}
          >
            {profile.is_doctor_role && (
              <Card className="p-space-4">
                <CardHeading icon={Laptop2} title="Qualifications" />
                <p className="text-ink-900 text-[13px] font-semibold">
                  {profile.qualification || "—"}
                </p>
              </Card>
            )}
            {profile.is_doctor_role && (
              <Card className="p-space-4">
                <CardHeading icon={Briefcase} title="Experience" />
                <p className="text-ink-900 text-[20px] font-bold">
                  {profile.years_experience != null ? profile.years_experience : "—"}
                  {profile.years_experience != null && (
                    <span className="ml-space-1 text-ink-400 text-[12px] font-medium">years</span>
                  )}
                </p>
                <p className="text-ink-400 text-[11.5px]">Total Clinical Experience</p>
              </Card>
            )}

            <Card className="p-space-4">
              <CardHeading icon={KeyRound} title="Change Password" />
              <form onSubmit={handleSubmit} className="gap-space-3 flex flex-col">
                <Field label="Current password" htmlFor="current_password" required>
                  <PasswordInput
                    id="current_password"
                    autoComplete="current-password"
                    required
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                  />
                </Field>
                <Field
                  label="New password"
                  htmlFor="new_password"
                  required
                  hint="At least 8 characters."
                >
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
                  <div className="border-error bg-error-tint p-space-3 text-error rounded-md border text-[12.5px]">
                    <ul className="pl-space-4 list-disc">
                      {errors.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <Button type="submit" disabled={submitting} className="self-start">
                  {submitting ? "Saving…" : "Change password"}
                </Button>
              </form>
            </Card>
          </div>
        </div>
      )}
    </PortalShell>
  );
}
