"use client";

import { useState } from "react";
import { Building2, CalendarClock, CalendarDays, FlaskConical, ListChecks, MapPin, Phone, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { AppointmentTypeToggles } from "@/components/portal/AppointmentTypeToggles";
import { DiagnosticTestsManager } from "@/components/portal/DiagnosticTestsManager";
import { GoogleCalendarCard } from "@/components/portal/GoogleCalendarCard";
import { LabServiceAreasManager } from "@/components/portal/LabServiceAreasManager";
import { LeavePolicyManager } from "@/components/portal/LeavePolicyManager";
import { usePortalSettings } from "@/hooks/usePortalSettings";
import type { PortalHospital } from "@/lib/portalAuth";
import { usePermission } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import {
  ADVANCE_BOOKING_DAYS_OPTIONS,
  BUFFER_MINUTES_OPTIONS,
  DURATION_MINUTES_OPTIONS,
  PASSWORD_EXPIRY_OPTIONS,
  SESSION_TIMEOUT_OPTIONS,
  initialGeneralSettings,
  type GeneralSettingsState,
} from "./general-settings-mock";
import {
  initialContactInformation,
  initialEmergencyContact,
  type ContactInformation,
  type EmergencyContact,
} from "./contact-info-mock";
import { SectionHeader, ToggleRow } from "./settings-ui";

function NumberSelect({
  value, onChange, options, suffix, disabled,
}: { value: number; onChange: (v: number) => void; options: number[]; suffix: string; disabled?: boolean }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      disabled={disabled}
      className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13.5px] text-ink-900 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {options.map((o) => (
        <option key={o} value={o}>{o} {suffix}</option>
      ))}
    </select>
  );
}

/** A real, already-persisted value (e.g. from usePortalSettings) may not be
 * one of this field's preset dropdown options -- ensures it's selectable
 * (shown in place, sorted in) instead of silently mismatching the <select>. */
function withValue(options: number[], value: number): number[] {
  return options.includes(value) ? options : [...options, value].sort((a, b) => a - b);
}

/** General tab of /portal/settings -- mostly a frontend-only mock rebuild of
 * the reference screenshot (Save/Reset just reset local state for most of
 * it). Hospital Name is NOT mock state -- it's read straight from the real,
 * already-loaded `hospital.name` (same read-only field the legacy settings
 * page used), so this tab doesn't grow a second, independently-editable
 * copy of it. Nine other fields are real, already-wired settings rather
 * than mock duplicates, all via usePortalSettings same as the legacy form:
 * "Advance Booking Limit" (`future_booking_days`), "Session Timeout"
 * (`session_timeout_minutes`), "Handoff Auto-Resolve" (`handoff_auto_
 * resolve_hours`) + "Require Patient Confirmation" (`require_patient_
 * confirmation`) -- conversation/session behavior, grouped into Security &
 * Session Settings rather than Notifications since neither is about
 * sending a message -- "Language" + "Ask patients to choose a language"
 * (`default_language`/`language_prompt_enabled`), and "Business Hours"
 * (`business_hours_text`, not in the mockup but a natural fit here).
 * Migration 20260914120000 made three more real: "Default Appointment
 * Duration" (`default_appointment_duration_minutes` -- the slot length
 * used for any doctor who hasn't set their own), "Buffer Time Between
 * Appointments" (`buffer_minutes` -- a gap enforced between every doctor's
 * consecutive candidate slots, hospital-wide), and "Maximum Appointments
 * Per Day" (`max_appointments_per_day` -- a hospital-wide daily booking
 * cap, enforced in create_appointment(); blank means no cap). The last one
 * also shows a live "X out of Y booked today" progress bar, from the same
 * GET response's read-only `appointments_today_count`.
 * Notification Preferences and message content (welcome/closing messages,
 * reminders) moved to the Notifications tab (see NotificationsTab.tsx).
 * Contact Information + Emergency Contact (frontend-only mock, combined
 * into one card here) live here too -- see contact-info-mock.ts's
 * initialContactInformation/initialEmergencyContact.
 *
 * Five more real, backend-wired sections moved over from the legacy page
 * (../_reference/legacy-general-settings-page.tsx), each just the same
 * component that page already used, gated by the same admin_capabilities/
 * permission checks: "Appointment Types" (AppointmentTypeToggles, kept as
 * its OWN card, deliberately separate from "Appointment Settings" above --
 * confirmed with the user that one is behavior/preferences, the other is
 * which types are enabled at all, and conflating them into one card was
 * confusing), "Diagnostic Tests" (DiagnosticTestsManager), "Leave Policy"
 * (LeavePolicyManager), "Lab Service Areas" (LabServiceAreasManager, the
 * PIN-code / home-collection settings), and Google Calendar
 * (GoogleCalendarCard, self-contained -- owns its own heading/copy/state).
 * Google Calendar briefly had its own Integrations tab but the user asked
 * to park it here for now until its real home is decided. */
export function GeneralSettingsTab({ hospital }: { hospital: PortalHospital | null }) {
  const [settings, setSettings] = useState<GeneralSettingsState>(initialGeneralSettings());
  const [contact, setContact] = useState<ContactInformation>(initialContactInformation());
  const [emergency, setEmergency] = useState<EmergencyContact>(initialEmergencyContact());
  const hospitalName = hospital?.name ?? "";
  // Same fail-open-while-loading convention the legacy page used (!hospital
  // means "still loading", not "no capabilities").
  const canManageAppointmentTypes = !hospital || hospital.admin_capabilities?.includes("manage_appointment_types");
  const canManageTests = !hospital || hospital.admin_capabilities?.includes("manage_diagnostic_resources");
  const canManageLeavePolicy = usePermission("leave_requests", "write");

  // `true` here (not a `ready` prop) is safe: GeneralSettingsTab only ever
  // mounts once PortalSettingsPage's own usePortalGuard is already ready.
  const {
    settings: portalSettings, setSettings: setPortalSettings, saving, saved, error, handleSave: savePortalSettings,
  } = usePortalSettings(true);

  function patch<K extends keyof GeneralSettingsState>(section: K, value: Partial<GeneralSettingsState[K]>) {
    setSettings((prev) => ({ ...prev, [section]: { ...prev[section], ...value } }));
  }

  function handleReset() {
    // Only resets the mock portion -- future_booking_days/session_timeout_
    // minutes are real, saved settings, not something a UI-only "reset to
    // default" button should silently overwrite.
    setSettings(initialGeneralSettings());
    setContact(initialContactInformation());
    setEmergency(initialEmergencyContact());
    toast.success("Reset to default", "General settings reverted to their defaults.");
  }

  // Real save/error/saved state comes from usePortalSettings (rendered
  // inline below, next to the buttons) -- a toast here would be a stale
  // read of `error`/`saved` from this render's closure, so it isn't one.
  async function handleSave(e: React.FormEvent) {
    await savePortalSettings(e);
  }

  const { appointments, security } = settings;

  return (
    <div className="flex flex-col gap-space-4">
      <form onSubmit={handleSave} className="flex flex-col gap-space-4">
      <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-2">
        <Card className="p-space-4">
          <SectionHeader icon={Building2} tint="brand" title="Hospital Information" subtitle="Basic information about your hospital" />
          <Field label="Hospital Name" required hint="Contact the platform team to change this.">
            <Input value={hospitalName} disabled />
          </Field>
          <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
            <Field label="Language" hint={!portalSettings ? "Loading…" : undefined}>
              <select
                value={portalSettings?.default_language ?? "en"}
                onChange={(e) =>
                  portalSettings && setPortalSettings({ ...portalSettings, default_language: e.target.value as "en" | "hi" })
                }
                disabled={!portalSettings}
                className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13.5px] text-ink-900 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="en">English</option>
                <option value="hi">हिन्दी (Hindi)</option>
              </select>
            </Field>
            <Field label="Business Hours" className="mb-0" hint={!portalSettings ? "Loading…" : "e.g. Mon-Sat, 9am-8pm"}>
              <Input
                value={portalSettings?.business_hours_text ?? ""}
                onChange={(e) => portalSettings && setPortalSettings({ ...portalSettings, business_hours_text: e.target.value })}
                disabled={!portalSettings}
              />
            </Field>
          </div>
          <ToggleRow
            label="Ask patients to choose a language"
            subtitle="Shown at the start of every fresh WhatsApp conversation"
            checked={portalSettings?.language_prompt_enabled ?? false}
            onChange={() =>
              portalSettings && setPortalSettings({ ...portalSettings, language_prompt_enabled: !portalSettings.language_prompt_enabled })
            }
            disabled={!portalSettings}
          />
        </Card>

        <Card className="p-space-4">
          <SectionHeader icon={Phone} tint="brand" title="Contact Information" subtitle="Primary and emergency contact details for your hospital" />
          <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
            <Field label="Phone Number" required>
              <Input value={contact.phone} onChange={(e) => setContact({ ...contact, phone: e.target.value })} />
            </Field>
            <Field label="Alternate Phone">
              <Input value={contact.alternatePhone} onChange={(e) => setContact({ ...contact, alternatePhone: e.target.value })} />
            </Field>
          </div>
          <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
            <Field label="Email Address" required>
              <Input type="email" value={contact.email} onChange={(e) => setContact({ ...contact, email: e.target.value })} />
            </Field>
            <Field label="Website">
              <Input value={contact.website} onChange={(e) => setContact({ ...contact, website: e.target.value })} />
            </Field>
          </div>
          <Field label="Address" required>
            <Textarea rows={2} value={contact.address} onChange={(e) => setContact({ ...contact, address: e.target.value })} />
          </Field>

          <div className="mt-space-4 border-t border-line pt-space-4">
            <p className="mb-space-3 text-[13px] font-bold text-ink-900">Emergency Contact</p>
            <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
              <Field label="Emergency Contact Number" required>
                <Input value={emergency.number} onChange={(e) => setEmergency({ ...emergency, number: e.target.value })} />
              </Field>
              <Field label="Contact Person" required>
                <Input value={emergency.contactPerson} onChange={(e) => setEmergency({ ...emergency, contactPerson: e.target.value })} />
              </Field>
            </div>
            <Field label="Designation" className="mb-0">
              <Input value={emergency.designation} onChange={(e) => setEmergency({ ...emergency, designation: e.target.value })} />
            </Field>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-2">
        <Card className="p-space-4">
          <SectionHeader icon={CalendarDays} tint="brand" title="Appointment Settings" subtitle="Configure appointment related preferences" />
          <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
            <Field
              label="Default Appointment Duration"
              hint={!portalSettings ? "Loading…" : "Used for any doctor who hasn't set their own slot length"}
            >
              <NumberSelect
                value={portalSettings?.default_appointment_duration_minutes ?? 30}
                onChange={(v) =>
                  portalSettings && setPortalSettings({ ...portalSettings, default_appointment_duration_minutes: v })
                }
                options={withValue(DURATION_MINUTES_OPTIONS, portalSettings?.default_appointment_duration_minutes ?? 30)}
                suffix="minutes"
                disabled={!portalSettings}
              />
            </Field>
            <Field
              label="Buffer Time Between Appointments"
              hint={!portalSettings ? "Loading…" : "Gap kept free between every doctor's back-to-back slots"}
            >
              <NumberSelect
                value={portalSettings?.buffer_minutes ?? 0}
                onChange={(v) => portalSettings && setPortalSettings({ ...portalSettings, buffer_minutes: v })}
                options={withValue(BUFFER_MINUTES_OPTIONS, portalSettings?.buffer_minutes ?? 0)}
                suffix="minutes"
                disabled={!portalSettings}
              />
            </Field>
            <Field label="Advance Booking Limit" hint={!portalSettings ? "Loading…" : undefined}>
              <NumberSelect
                value={portalSettings?.future_booking_days ?? 90}
                onChange={(v) => portalSettings && setPortalSettings({ ...portalSettings, future_booking_days: v })}
                options={withValue(ADVANCE_BOOKING_DAYS_OPTIONS, portalSettings?.future_booking_days ?? 90)}
                suffix="days"
                disabled={!portalSettings}
              />
            </Field>
            <Field label="Maximum Appointments Per Day" hint={!portalSettings ? "Loading…" : "Leave blank for no daily cap"}>
              <Input
                type="number"
                min={1}
                placeholder="No limit"
                value={portalSettings?.max_appointments_per_day ?? ""}
                onChange={(e) =>
                  portalSettings &&
                  setPortalSettings({
                    ...portalSettings,
                    max_appointments_per_day: e.target.value === "" ? "" : Number(e.target.value),
                  })
                }
                disabled={!portalSettings}
              />
            </Field>
          </div>
          {portalSettings && portalSettings.max_appointments_per_day !== "" && (
            <div className="mt-space-2">
              <div className="mb-space-1 flex items-center justify-between text-[12px] text-ink-400">
                <span>Booked today</span>
                <span className="font-semibold text-ink-700">
                  {portalSettings.appointments_today_count} out of {portalSettings.max_appointments_per_day}
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-black/6">
                <div
                  className="h-full rounded-full bg-brand-600"
                  style={{
                    width: `${Math.min(
                      100,
                      (portalSettings.appointments_today_count / (portalSettings.max_appointments_per_day || 1)) * 100,
                    )}%`,
                  }}
                />
              </div>
            </div>
          )}
          <div className="mt-space-2">
            <ToggleRow
              label="Allow Online Appointments"
              subtitle="Patients can self-book via WhatsApp"
              checked={appointments.allowOnlineAppointments}
              onChange={() => patch("appointments", { allowOnlineAppointments: !appointments.allowOnlineAppointments })}
            />
            <ToggleRow
              label="Send Appointment Reminders"
              subtitle="Automatic WhatsApp reminders"
              checked={appointments.sendReminders}
              onChange={() => patch("appointments", { sendReminders: !appointments.sendReminders })}
            />
          </div>
        </Card>

        <Card className="p-space-4">
          <SectionHeader icon={ShieldCheck} tint="error" title="Security & Session Settings" subtitle="Manage security preferences" />
          <div className="mb-space-3 grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
            <Field label="Session Timeout" hint={!portalSettings ? "Loading…" : undefined}>
              <NumberSelect
                value={portalSettings?.session_timeout_minutes ?? 30}
                onChange={(v) => portalSettings && setPortalSettings({ ...portalSettings, session_timeout_minutes: v })}
                options={withValue(SESSION_TIMEOUT_OPTIONS, portalSettings?.session_timeout_minutes ?? 30)}
                suffix="minutes"
                disabled={!portalSettings}
              />
            </Field>
            <Field label="Handoff Auto-Resolve" hint={!portalSettings ? "Loading…" : "Between 1 and 168 hours"}>
              <Input
                type="number"
                min={1}
                max={168}
                value={portalSettings?.handoff_auto_resolve_hours ?? 24}
                onChange={(e) =>
                  portalSettings && setPortalSettings({ ...portalSettings, handoff_auto_resolve_hours: Number(e.target.value) })
                }
                disabled={!portalSettings}
              />
            </Field>
          </div>
          <ToggleRow
            label="Require Patient Confirmation"
            subtitle="Ask for explicit confirmation before entering the menu, even for a single linked patient"
            checked={portalSettings?.require_patient_confirmation ?? false}
            onChange={() =>
              portalSettings && setPortalSettings({ ...portalSettings, require_patient_confirmation: !portalSettings.require_patient_confirmation })
            }
            disabled={!portalSettings}
          />
          <div className="mb-space-3 mt-space-3 grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
            <Field label="Password Expiry">
              <NumberSelect
                value={security.passwordExpiryDays}
                onChange={(v) => patch("security", { passwordExpiryDays: v })}
                options={PASSWORD_EXPIRY_OPTIONS}
                suffix="days"
              />
            </Field>
          </div>
          <div className="divide-y divide-line">
            <ToggleRow
              label="Allow Multiple Sessions"
              subtitle="Sign in from more than one device"
              checked={security.allowMultipleSessions}
              onChange={() => patch("security", { allowMultipleSessions: !security.allowMultipleSessions })}
            />
            <ToggleRow
              label="Log User Activities"
              subtitle="Keep an audit trail of staff actions"
              checked={security.logUserActivities}
              onChange={() => patch("security", { logUserActivities: !security.logUserActivities })}
            />
          </div>
          <div className="mt-space-3 flex items-start gap-space-2 rounded-md bg-brand-50 p-space-3">
            <ShieldCheck size={16} className="mt-0.5 shrink-0 text-brand-600" />
            <p className="text-[12px] text-ink-700">
              <span className="font-bold">Keep your account secure. </span>
              Regularly update your security settings to protect patient data.
            </p>
          </div>
        </Card>
      </div>

      <div className="flex flex-wrap items-center justify-end gap-space-2">
        {error && <p className="mr-auto text-[12.5px] font-medium text-error">{error}</p>}
        {saved && !error && <p className="mr-auto text-[12.5px] font-medium text-success">Saved.</p>}
        <Button type="button" variant="secondary" onClick={handleReset}>Reset to Default</Button>
        <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Save Changes"}</Button>
      </div>
    </form>

    {/* The sections below are each their own independent, real, already-
        wired manager (some with their own <form>, e.g. LeavePolicyManager)
        -- deliberately OUTSIDE the form above (nested <form>s are invalid
        HTML and break hydration) and not tied to its Save/Reset button. */}
    {canManageAppointmentTypes && (
        <Card className="p-space-4">
          <SectionHeader
            icon={ListChecks}
            tint="brand"
            title="Appointment Types"
            subtitle="Which booking types patients can choose -- separate from the general appointment settings above"
          />
          <p className="mb-space-3 text-[12.5px] text-ink-400">
            The card above (&quot;Appointment Settings&quot;) controls HOW appointments behave -- duration,
            buffer time, approval, reminders. This one controls WHICH appointment types show up at all in the
            WhatsApp booking menu (e.g. Doctor Consultation, Daycare, Diagnostic Test). Turn a type off here and
            patients simply won&apos;t see it as an option. A type greyed out below hasn&apos;t been enabled for
            your account by the platform -- contact support to request it.
          </p>
          <AppointmentTypeToggles canManage={!!canManageAppointmentTypes} />
        </Card>
      )}

      <Card className="p-space-4">
        <SectionHeader
          icon={FlaskConical}
          tint="success"
          title="Diagnostic Tests"
          subtitle="Manage the tests patients can book under Diagnostic Test / Lab Test, each with its own weekly schedule"
        />
        <DiagnosticTestsManager canManage={!!canManageTests} />
      </Card>

      <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-2">
        <Card className="p-space-4">
          <SectionHeader
            icon={CalendarClock}
            tint="clay"
            title="Leave Policy"
            subtitle="Annual leave allowance the Leave Requests / Holiday Application pages compute balances against"
          />
          <LeavePolicyManager canManage={canManageLeavePolicy} />
        </Card>

        {canManageAppointmentTypes && (
          <Card className="p-space-4">
            <SectionHeader
              icon={MapPin}
              tint="error"
              title="Lab Service Areas"
              subtitle="PIN codes where you offer Home Sample Collection for Lab Test bookings"
            />
            <p className="mb-space-3 text-[12.5px] text-ink-400">
              A patient entering a PIN code not listed here is offered Visit Hospital/Lab instead of Home
              Collection.
            </p>
            <LabServiceAreasManager canManage={!!canManageAppointmentTypes} />
          </Card>
        )}
      </div>

      <Card className="p-space-4">
        <GoogleCalendarCard />
      </Card>
    </div>
  );
}
