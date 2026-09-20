"use client";

import { useState } from "react";
import { Building2, CalendarClock, Phone, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { GoogleCalendarCard } from "@/components/portal/GoogleCalendarCard";
import { LeavePolicyManager } from "@/components/portal/LeavePolicyManager";
import { usePortalSettings } from "@/hooks/usePortalSettings";
import type { PortalHospital } from "@/lib/portalAuth";
import { usePermission } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import {
  PASSWORD_EXPIRY_OPTIONS,
  SESSION_TIMEOUT_OPTIONS,
  initialGeneralSettings,
  type GeneralSettingsState,
} from "./general-settings-mock";
import { NumberSelect, SectionHeader, ToggleRow, withValue } from "./settings-ui";

/** General tab of /portal/settings. Hospital Name is read straight from
 * the real, already-loaded `hospital.name` (read-only). Session Timeout,
 * Handoff Auto-Resolve, Show Patient Name on Entry, Language, Business
 * Hours, Welcome message, and the whole Contact Information card (Phone
 * Number/Alternate Phone/Email/Address/Emergency Contact) are real,
 * backend-wired via usePortalSettings, stored on `hospitals` (not
 * hospital_settings -- confirmed with the user, this is hospital identity/
 * profile data, same category as name/timezone). Contact Information used
 * to be entirely frontend-only mock state (contact-info-mock.ts, now
 * deleted) with no backend effect at all -- made real minus its old
 * "Website" field, which was dropped rather than made real. Only the
 * three hidden Security toggles below (Password Expiry/Allow Multiple
 * Sessions/Log User Activities) are still frontend-only mock state.
 * Welcome message lives here (Hospital Information card) rather than on
 * the Notifications tab -- it's hospital-identity content, not a
 * notification setting. Notification Preferences live on the
 * Notifications tab (see NotificationsTab.tsx). Appointment Settings,
 * Follow-up & Fees, Appointment Types, Diagnostic Tests, and Lab Service
 * Areas all moved to their own Appointments tab (see AppointmentsTab.tsx)
 * -- General had grown five appointment-related sections crammed in
 * alongside Hospital Information/Contact/Security, confirmed messy with
 * the user. Leave Policy and Google Calendar stayed here since neither is
 * specifically appointment-related (staff leave policy; a per-hospital
 * integration), gated by the relevant admin_capabilities/permission
 * checks. */
export function GeneralSettingsTab({ hospital }: { hospital: PortalHospital | null }) {
  const [settings, setSettings] = useState<GeneralSettingsState>(initialGeneralSettings());
  const hospitalName = hospital?.name ?? "";
  const canManageLeavePolicy = usePermission("leave_requests", "write");

  // `true` here (not a `ready` prop) is safe: GeneralSettingsTab only ever
  // mounts once PortalSettingsPage's own usePortalGuard is already ready.
  const {
    settings: portalSettings,
    setSettings: setPortalSettings,
    saving,
    saved,
    error,
    handleSave: savePortalSettings,
  } = usePortalSettings(true);

  function patch<K extends keyof GeneralSettingsState>(
    section: K,
    value: Partial<GeneralSettingsState[K]>,
  ) {
    setSettings((prev) => ({ ...prev, [section]: { ...prev[section], ...value } }));
  }

  function handleReset() {
    // Only resets the mock portion -- everything else on this tab
    // (Contact Information/Emergency Contact included, now real) is a
    // saved backend setting, not something a UI-only "reset to default"
    // button should silently overwrite.
    setSettings(initialGeneralSettings());
    toast.success("Reset to default", "General settings reverted to their defaults.");
  }

  // Real save/error/saved state comes from usePortalSettings (rendered
  // inline below, next to the buttons) -- a toast here would be a stale
  // read of `error`/`saved` from this render's closure, so it isn't one.
  async function handleSave(e: React.FormEvent) {
    await savePortalSettings(e);
  }

  const { security } = settings;

  return (
    <div className="gap-space-4 flex flex-col">
      <form onSubmit={handleSave} className="gap-space-4 flex flex-col">
        <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-2">
          <Card className="p-space-4">
            <SectionHeader
              icon={Building2}
              tint="brand"
              title="Hospital Information"
              subtitle="Basic information about your hospital"
            />
            <Field label="Hospital Name" required hint="Contact the platform team to change this.">
              <Input value={hospitalName} disabled />
            </Field>
            <div className="gap-x-space-3 grid grid-cols-1 sm:grid-cols-2">
              <Field
                label="Language"
                hint={
                  !portalSettings
                    ? "Loading…"
                    : "Used as the conversation language when the toggle below is off."
                }
              >
                <select
                  value={portalSettings?.default_language ?? "en"}
                  onChange={(e) =>
                    portalSettings &&
                    setPortalSettings({
                      ...portalSettings,
                      default_language: e.target.value as "en" | "hi",
                    })
                  }
                  disabled={!portalSettings}
                  className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="en">English</option>
                  <option value="hi">हिन्दी (Hindi)</option>
                </select>
              </Field>
              <Field
                label="Business Hours"
                className="mb-0"
                hint={
                  !portalSettings
                    ? "Loading…"
                    : 'e.g. Mon-Sat, 9am-8pm — shown under "Hospital Info" in the WhatsApp menu.'
                }
              >
                <Input
                  value={portalSettings?.business_hours_text ?? ""}
                  onChange={(e) =>
                    portalSettings &&
                    setPortalSettings({ ...portalSettings, business_hours_text: e.target.value })
                  }
                  disabled={!portalSettings}
                />
              </Field>
            </div>
            <ToggleRow
              label="Ask patients to choose a language"
              subtitle="Shown at the start of every fresh WhatsApp conversation; off uses Language above directly."
              checked={portalSettings?.language_prompt_enabled ?? false}
              onChange={() =>
                portalSettings &&
                setPortalSettings({
                  ...portalSettings,
                  language_prompt_enabled: !portalSettings.language_prompt_enabled,
                })
              }
              disabled={!portalSettings}
            />
            <Field
              label="Welcome message"
              htmlFor="welcome_message_text"
              className="mb-0"
              hint={
                !portalSettings
                  ? "Loading…"
                  : "Shown when a patient's conversation starts. Leave blank to show a default greeting with your hospital's name."
              }
            >
              <Textarea
                id="welcome_message_text"
                rows={2}
                value={portalSettings?.welcome_message_text ?? ""}
                onChange={(e) =>
                  portalSettings &&
                  setPortalSettings({ ...portalSettings, welcome_message_text: e.target.value })
                }
                disabled={!portalSettings}
              />
            </Field>
          </Card>

          <Card className="p-space-4">
            <SectionHeader
              icon={Phone}
              tint="brand"
              title="Contact Information"
              subtitle="Primary and emergency contact details for your hospital"
            />
            <div className="gap-x-space-3 grid grid-cols-1 sm:grid-cols-2">
              <Field label="Phone Number" hint={!portalSettings ? "Loading…" : undefined}>
                <Input
                  value={portalSettings?.contact_phone ?? ""}
                  onChange={(e) =>
                    portalSettings &&
                    setPortalSettings({ ...portalSettings, contact_phone: e.target.value })
                  }
                  disabled={!portalSettings}
                />
              </Field>
              <Field label="Alternate Phone">
                <Input
                  value={portalSettings?.contact_alternate_phone ?? ""}
                  onChange={(e) =>
                    portalSettings &&
                    setPortalSettings({
                      ...portalSettings,
                      contact_alternate_phone: e.target.value,
                    })
                  }
                  disabled={!portalSettings}
                />
              </Field>
            </div>
            <Field label="Email Address" className="mb-space-4">
              <Input
                type="email"
                value={portalSettings?.contact_email ?? ""}
                onChange={(e) =>
                  portalSettings &&
                  setPortalSettings({ ...portalSettings, contact_email: e.target.value })
                }
                disabled={!portalSettings}
              />
            </Field>
            <Field label="Address">
              <Textarea
                rows={2}
                value={portalSettings?.contact_address ?? ""}
                onChange={(e) =>
                  portalSettings &&
                  setPortalSettings({ ...portalSettings, contact_address: e.target.value })
                }
                disabled={!portalSettings}
              />
            </Field>

            <div className="mt-space-4 border-line pt-space-4 border-t">
              <p className="mb-space-3 text-ink-900 text-[13px] font-bold">Emergency Contact</p>
              <div className="gap-x-space-3 grid grid-cols-1 sm:grid-cols-2">
                <Field label="Emergency Contact Number">
                  <Input
                    value={portalSettings?.emergency_contact_number ?? ""}
                    onChange={(e) =>
                      portalSettings &&
                      setPortalSettings({
                        ...portalSettings,
                        emergency_contact_number: e.target.value,
                      })
                    }
                    disabled={!portalSettings}
                  />
                </Field>
                <Field label="Contact Person">
                  <Input
                    value={portalSettings?.emergency_contact_person ?? ""}
                    onChange={(e) =>
                      portalSettings &&
                      setPortalSettings({
                        ...portalSettings,
                        emergency_contact_person: e.target.value,
                      })
                    }
                    disabled={!portalSettings}
                  />
                </Field>
              </div>
              <Field label="Designation" className="mb-0">
                <Input
                  value={portalSettings?.emergency_contact_designation ?? ""}
                  onChange={(e) =>
                    portalSettings &&
                    setPortalSettings({
                      ...portalSettings,
                      emergency_contact_designation: e.target.value,
                    })
                  }
                  disabled={!portalSettings}
                />
              </Field>
            </div>
          </Card>
        </div>

        <Card className="p-space-4">
          <SectionHeader
            icon={ShieldCheck}
            tint="error"
            title="Security & Session Settings"
            subtitle="Manage security preferences"
          />
          <div className="mb-space-3 gap-x-space-3 grid grid-cols-1 sm:grid-cols-2">
            <Field label="Session Timeout" hint={!portalSettings ? "Loading…" : undefined}>
              <NumberSelect
                value={portalSettings?.session_timeout_minutes ?? 30}
                onChange={(v) =>
                  portalSettings &&
                  setPortalSettings({ ...portalSettings, session_timeout_minutes: v })
                }
                options={withValue(
                  SESSION_TIMEOUT_OPTIONS,
                  portalSettings?.session_timeout_minutes ?? 30,
                )}
                suffix="minutes"
                disabled={!portalSettings}
              />
            </Field>
            <Field
              label="Handoff Auto-Resolve"
              hint={!portalSettings ? "Loading…" : "Between 1 and 168 hours"}
            >
              <Input
                type="number"
                min={1}
                max={168}
                value={portalSettings?.handoff_auto_resolve_hours ?? 24}
                onChange={(e) =>
                  portalSettings &&
                  setPortalSettings({
                    ...portalSettings,
                    handoff_auto_resolve_hours: Number(e.target.value),
                  })
                }
                disabled={!portalSettings}
              />
            </Field>
          </div>
          <ToggleRow
            label="Show Patient Name on Entry"
            subtitle="Greets a single linked patient by name (with an Add Patient option) instead of the plain main menu -- doesn't block or delay entry"
            checked={portalSettings?.require_patient_confirmation ?? false}
            onChange={() =>
              portalSettings &&
              setPortalSettings({
                ...portalSettings,
                require_patient_confirmation: !portalSettings.require_patient_confirmation,
              })
            }
            disabled={!portalSettings}
          />
          {/* Hidden for now (confirmed with the user) -- all three are
            frontend-only mock state (security.*, GeneralSettingsState),
            never sent to the backend or enforced anywhere.
          <div className="mb-space-3 mt-space-3 gap-x-space-3 grid grid-cols-1 sm:grid-cols-2">
            <Field label="Password Expiry">
              <NumberSelect
                value={security.passwordExpiryDays}
                onChange={(v) => patch("security", { passwordExpiryDays: v })}
                options={PASSWORD_EXPIRY_OPTIONS}
                suffix="days"
              />
            </Field>
          </div>
          <div className="divide-line divide-y">
            <ToggleRow
              label="Allow Multiple Sessions"
              subtitle="Sign in from more than one device"
              checked={security.allowMultipleSessions}
              onChange={() =>
                patch("security", { allowMultipleSessions: !security.allowMultipleSessions })
              }
            />
            <ToggleRow
              label="Log User Activities"
              subtitle="Keep an audit trail of staff actions"
              checked={security.logUserActivities}
              onChange={() => patch("security", { logUserActivities: !security.logUserActivities })}
            />
          </div>
          */}
          {/* <div className="mt-space-3 gap-space-2 bg-brand-50 p-space-3 flex items-start rounded-md">
            <ShieldCheck size={16} className="text-brand-600 mt-0.5 shrink-0" />
            <p className="text-ink-700 text-[12px]">
              <span className="font-bold">Keep your account secure. </span>
              Regularly update your security settings to protect patient data.
            </p>
          </div> */}
        </Card>

        <div className="gap-space-2 flex flex-wrap items-center justify-end">
          {error && <p className="text-error mr-auto text-[12.5px] font-medium">{error}</p>}
          {saved && !error && (
            <p className="text-success mr-auto text-[12.5px] font-medium">Saved.</p>
          )}
          <Button type="button" variant="secondary" onClick={handleReset}>
            Reset to Default
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save Changes"}
          </Button>
        </div>
      </form>

      {/* Leave Policy/Google Calendar are each their own independent, real,
        already-wired manager (LeavePolicyManager has its own <form>) --
        deliberately OUTSIDE the form above (nested <form>s are invalid HTML
        and break hydration) and not tied to its Save/Reset button. */}
      <Card className="p-space-4">
        <SectionHeader
          icon={CalendarClock}
          tint="clay"
          title="Leave Policy"
          subtitle="Annual leave allowance and leave types for the Leave Requests / Holiday Application pages"
        />
        <LeavePolicyManager canManage={canManageLeavePolicy} />
      </Card>

      <Card className="p-space-4">
        <GoogleCalendarCard />
      </Card>
    </div>
  );
}
