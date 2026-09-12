"use client";

import { useRef, useState } from "react";
import {
  Bell,
  Building2,
  CalendarDays,
  Image as ImageIcon,
  MessageCircle,
  Pencil,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { Switch } from "@/components/ui/Switch";
import { usePortalSettings } from "@/hooks/usePortalSettings";
import { toast } from "@/lib/toast";
import {
  ADVANCE_BOOKING_DAYS_OPTIONS,
  BUFFER_MINUTES_OPTIONS,
  DATE_FORMAT_OPTIONS,
  DURATION_MINUTES_OPTIONS,
  MAX_PER_DAY_OPTIONS,
  PASSWORD_EXPIRY_OPTIONS,
  SESSION_TIMEOUT_OPTIONS,
  TIMEZONE_OPTIONS,
  initialGeneralSettings,
  type GeneralSettingsState,
} from "./general-settings-mock";
import { Select, SectionHeader, ToggleRow } from "./settings-ui";

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

function ColorField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const colorInputRef = useRef<HTMLInputElement>(null);
  return (
    <div>
      <label className="text-label mb-space-1 block">{label}</label>
      <div className="flex items-center gap-space-2">
        <button
          type="button"
          onClick={() => colorInputRef.current?.click()}
          className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line"
          style={{ backgroundColor: value }}
          aria-label={`Change ${label.toLowerCase()}`}
        >
          <Pencil size={11} className="text-white drop-shadow" />
          <input
            ref={colorInputRef}
            type="color"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
          />
        </button>
        <Input value={value} onChange={(e) => onChange(e.target.value)} className="uppercase" />
      </div>
    </div>
  );
}

/** General tab of /portal/settings -- mostly a frontend-only mock rebuild of
 * the reference screenshot (Save/Reset just reset local state for most of
 * it). Four fields are real, already-wired settings rather than mock
 * duplicates, all via usePortalSettings same as the legacy form: "Advance
 * Booking Limit" (`future_booking_days`), "Session Timeout" (`session_
 * timeout_minutes`), "Language" + "Ask patients to choose a language"
 * (`default_language`/`language_prompt_enabled`), and "Business Hours"
 * (`business_hours_text`, not in the mockup but a natural fit here). The
 * rest of the prior real settings (welcome/closing messages, privacy
 * notice, diagnostic tests, leave policy, appointment types, Google
 * Calendar, lab service areas...) still exists in full at ../_reference/
 * legacy-general-settings-page.tsx -- still needs a home somewhere in this
 * new tab structure, just not decided yet. */
export function GeneralSettingsTab() {
  const [settings, setSettings] = useState<GeneralSettingsState>(initialGeneralSettings());
  const [logoDataUrl, setLogoDataUrl] = useState<string | null>(null);
  const logoInputRef = useRef<HTMLInputElement>(null);

  // `true` here (not a `ready` prop) is safe: GeneralSettingsTab only ever
  // mounts once PortalSettingsPage's own usePortalGuard is already ready.
  const {
    settings: portalSettings, setSettings: setPortalSettings, saving, saved, error, handleSave: savePortalSettings,
  } = usePortalSettings(true);

  function patch<K extends keyof GeneralSettingsState>(section: K, value: Partial<GeneralSettingsState[K]>) {
    setSettings((prev) => ({ ...prev, [section]: { ...prev[section], ...value } }));
  }

  function handleLogoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setLogoDataUrl(typeof reader.result === "string" ? reader.result : null);
    reader.readAsDataURL(file);
  }

  function handleTestConnection() {
    toast.success("Connection test successful", "WhatsApp Business API responded (mock).");
  }

  function handleReset() {
    // Only resets the mock portion -- future_booking_days/session_timeout_
    // minutes are real, saved settings, not something a UI-only "reset to
    // default" button should silently overwrite.
    setSettings(initialGeneralSettings());
    setLogoDataUrl(null);
    toast.success("Reset to default", "General settings reverted to their defaults.");
  }

  // Real save/error/saved state comes from usePortalSettings (rendered
  // inline below, next to the buttons) -- a toast here would be a stale
  // read of `error`/`saved` from this render's closure, so it isn't one.
  async function handleSave(e: React.FormEvent) {
    await savePortalSettings(e);
  }

  const { hospitalInfo, branding, whatsapp, appointments, notifications, security } = settings;

  return (
    <form onSubmit={handleSave} className="flex flex-col gap-space-4">
      <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-3">
        <Card className="p-space-4">
          <SectionHeader icon={Building2} tint="brand" title="Hospital Information" subtitle="Basic information about your hospital" />
          <Field label="Hospital Name" required>
            <Input value={hospitalInfo.name} onChange={(e) => patch("hospitalInfo", { name: e.target.value })} />
          </Field>
          <Field label="Address" required>
            <Textarea rows={2} value={hospitalInfo.address} onChange={(e) => patch("hospitalInfo", { address: e.target.value })} />
          </Field>
          <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
            <Field label="Phone Number" required>
              <Input value={hospitalInfo.phone} onChange={(e) => patch("hospitalInfo", { phone: e.target.value })} />
            </Field>
            <Field label="Email Address" required>
              <Input type="email" value={hospitalInfo.email} onChange={(e) => patch("hospitalInfo", { email: e.target.value })} />
            </Field>
          </div>
          <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
            <Field label="Timezone">
              <Select value={hospitalInfo.timezone} onChange={(v) => patch("hospitalInfo", { timezone: v })} options={TIMEZONE_OPTIONS} />
            </Field>
            <Field label="Date Format">
              <Select value={hospitalInfo.dateFormat} onChange={(v) => patch("hospitalInfo", { dateFormat: v })} options={DATE_FORMAT_OPTIONS} />
            </Field>
          </div>
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
          <SectionHeader icon={ImageIcon} tint="clay" title="Hospital Branding" subtitle="Upload your hospital logo and branding" />
          <Field label="">
            <div className="flex items-center gap-space-3 rounded-md border border-dashed border-line p-space-3">
              <span className="flex h-11 w-16 shrink-0 items-center justify-center overflow-hidden rounded-md bg-brand-50 text-brand-600">
                {logoDataUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={logoDataUrl} alt="Hospital logo" className="h-full w-full object-contain" />
                ) : (
                  <ImageIcon size={18} />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-bold text-ink-900">{hospitalInfo.name}</p>
                <p className="truncate text-hint">{branding.tagline}</p>
              </div>
              <Button type="button" variant="secondary" size="md" onClick={() => logoInputRef.current?.click()} className="shrink-0">
                <Upload size={14} /> Change Logo
              </Button>
              <input ref={logoInputRef} type="file" accept="image/*" onChange={handleLogoChange} className="hidden" />
            </div>
            <p className="text-hint mt-space-1">Recommended size: 300 x 100 px. PNG, JPG or SVG (Max 2 MB).</p>
          </Field>
          <div className="grid grid-cols-1 gap-x-space-3 gap-y-space-3 sm:grid-cols-2">
            <ColorField label="Primary Brand Color" value={branding.primaryColor} onChange={(v) => patch("branding", { primaryColor: v })} />
            <ColorField label="Secondary Color" value={branding.secondaryColor} onChange={(v) => patch("branding", { secondaryColor: v })} />
          </div>
          <Field label="Hospital Tagline" className="mb-0 mt-space-3">
            <Input value={branding.tagline} onChange={(e) => patch("branding", { tagline: e.target.value })} />
          </Field>
        </Card>

        <Card className="p-space-4">
          <SectionHeader icon={MessageCircle} tint="success" title="WhatsApp Configuration" subtitle="Configure WhatsApp for patient communications" />
          <div className="mb-space-3 flex items-center justify-between">
            <span className="text-[13px] font-semibold text-ink-900">Enable WhatsApp Integration</span>
            <Switch checked={whatsapp.enabled} onChange={() => patch("whatsapp", { enabled: !whatsapp.enabled })} />
          </div>
          <Field label="WhatsApp Business Number">
            <Input value={whatsapp.businessNumber} onChange={(e) => patch("whatsapp", { businessNumber: e.target.value })} />
          </Field>
          <Field label="API Key" className="mb-0">
            <PasswordInput value={whatsapp.apiKey} onChange={(e) => patch("whatsapp", { apiKey: e.target.value })} />
          </Field>
          {whatsapp.connected && (
            <div className="mt-space-3 flex flex-wrap items-center justify-between gap-space-2 rounded-md bg-success-tint p-space-3">
              <div className="min-w-0">
                <p className="text-[13px] font-bold text-success">Connected</p>
                <p className="truncate text-[12px] text-ink-600">Last synced: {whatsapp.lastSyncedAt}</p>
              </div>
              <Button type="button" variant="secondary" size="md" onClick={handleTestConnection}>
                Test Connection
              </Button>
            </div>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-3">
        <Card className="p-space-4">
          <SectionHeader icon={CalendarDays} tint="brand" title="Appointment Settings" subtitle="Configure appointment related preferences" />
          <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
            <Field label="Default Appointment Duration">
              <NumberSelect
                value={appointments.defaultDurationMinutes}
                onChange={(v) => patch("appointments", { defaultDurationMinutes: v })}
                options={DURATION_MINUTES_OPTIONS}
                suffix="minutes"
              />
            </Field>
            <Field label="Buffer Time Between Appointments">
              <NumberSelect
                value={appointments.bufferMinutes}
                onChange={(v) => patch("appointments", { bufferMinutes: v })}
                options={BUFFER_MINUTES_OPTIONS}
                suffix="minutes"
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
            <Field label="Maximum Appointments Per Day">
              <NumberSelect
                value={appointments.maxAppointmentsPerDay}
                onChange={(v) => patch("appointments", { maxAppointmentsPerDay: v })}
                options={MAX_PER_DAY_OPTIONS}
                suffix=""
              />
            </Field>
          </div>
          <div className="mt-space-2">
            <ToggleRow
              label="Allow Online Appointments"
              subtitle="Patients can self-book via WhatsApp"
              checked={appointments.allowOnlineAppointments}
              onChange={() => patch("appointments", { allowOnlineAppointments: !appointments.allowOnlineAppointments })}
            />
            <ToggleRow
              label="Require Appointment Approval"
              subtitle="Staff must confirm before it's booked"
              checked={appointments.requireApproval}
              onChange={() => patch("appointments", { requireApproval: !appointments.requireApproval })}
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
          <SectionHeader icon={Bell} tint="clay" title="Notification Preferences" subtitle="Choose how and when to send notifications" />
          <div className="divide-y divide-line">
            <ToggleRow
              label="Appointment Confirmations"
              subtitle="Notify patients when appointment is confirmed"
              checked={notifications.appointmentConfirmations}
              onChange={() => patch("notifications", { appointmentConfirmations: !notifications.appointmentConfirmations })}
            />
            <ToggleRow
              label="Appointment Reminders"
              subtitle="Send reminder before appointment"
              checked={notifications.appointmentReminders}
              onChange={() => patch("notifications", { appointmentReminders: !notifications.appointmentReminders })}
            />
            <ToggleRow
              label="Follow-up Reminders"
              subtitle="Notify for follow-up appointments"
              checked={notifications.followUpReminders}
              onChange={() => patch("notifications", { followUpReminders: !notifications.followUpReminders })}
            />
            <ToggleRow
              label="Lab Report Notifications"
              subtitle="Notify when lab reports are ready"
              checked={notifications.labReportNotifications}
              onChange={() => patch("notifications", { labReportNotifications: !notifications.labReportNotifications })}
            />
            <ToggleRow
              label="System Announcements"
              subtitle="Important updates and maintenance"
              checked={notifications.systemAnnouncements}
              onChange={() => patch("notifications", { systemAnnouncements: !notifications.systemAnnouncements })}
            />
            <ToggleRow
              label="Marketing Communications"
              subtitle="Send health tips and newsletters"
              checked={notifications.marketingCommunications}
              onChange={() => patch("notifications", { marketingCommunications: !notifications.marketingCommunications })}
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
              label="Require Two-Factor Authentication (2FA)"
              subtitle="Extra verification step at login"
              checked={security.requireTwoFactor}
              onChange={() => patch("security", { requireTwoFactor: !security.requireTwoFactor })}
            />
            <ToggleRow
              label="Enforce Strong Password Policy"
              subtitle="Minimum length + complexity rules"
              checked={security.enforceStrongPassword}
              onChange={() => patch("security", { enforceStrongPassword: !security.enforceStrongPassword })}
            />
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
  );
}
