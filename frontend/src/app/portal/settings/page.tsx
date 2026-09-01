"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CheckboxRow } from "@/components/ui/Checkbox";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { AppointmentTypeToggles } from "@/components/portal/AppointmentTypeToggles";
import { DaycareDurationOptions } from "@/components/portal/DaycareDurationOptions";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { portalFetch } from "@/lib/portalAuth";

type Settings = {
  name: string;
  welcome_message_text: string;
  reminder_offsets_hours: string;
  reminder_template_name: string;
  // Section 12.13: self-serve bot customization.
  enabled_features: string[];
  closing_message_text: string;
  business_hours_text: string;
  default_language: "en" | "hi";
  language_prompt_enabled: boolean;
  session_timeout_minutes: number;
  // Messages page follow-up: how long an open "Talk to Reception" handoff
  // can go with no activity from either side before it auto-resolves.
  handoff_auto_resolve_hours: number;
  // CareConnect architecture doc alignment (Spec.md Section 0).
  require_patient_confirmation: boolean;
  privacy_notice_text: string;
};

type AuditEntry = {
  id: number;
  actor_level: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  before_value: Record<string, unknown> | null;
  after_value: Record<string, unknown> | null;
  created_at: string;
};

function formatAuditChanges(entry: AuditEntry): string {
  const keys = new Set([
    ...Object.keys(entry.before_value || {}),
    ...Object.keys(entry.after_value || {}),
  ]);
  if (keys.size === 0) return "";
  return Array.from(keys)
    .map((key) => {
      const before = entry.before_value?.[key];
      const after = entry.after_value?.[key];
      if (before !== undefined && after !== undefined) return `${key}: ${JSON.stringify(before)} → ${JSON.stringify(after)}`;
      if (after !== undefined) return `${key}: ${JSON.stringify(after)}`;
      return `${key}: ${JSON.stringify(before)}`;
    })
    .join(", ");
}

export default function PortalSettingsPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
  // Backend route guards already 403 the actual mutations for a clinic
  // tenant lacking manage_appointment_types -- same UI-convenience-only
  // gating as PortalDoctorsPage's canManageDoctors. Fails open (renders the
  // section) while hospital hasn't loaded yet.
  const canManageAppointmentTypes = !hospital || hospital.admin_capabilities?.includes("manage_appointment_types");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  // undefined = not loaded yet, null = this tenant lacks manage_settings (the
  // capability that also gates the settings-update route above) so the
  // section is hidden rather than shown as an error.
  const [auditEntries, setAuditEntries] = useState<AuditEntry[] | null | undefined>(undefined);

  const load = useCallback(async () => {
    const result = await portalFetch("/api/portal/settings");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setSettings(result.data as Settings);
  }, [router]);

  const loadAuditLog = useCallback(async () => {
    const result = await portalFetch("/api/portal/audit-log");
    if (!result.ok) {
      // 403 (no manage_settings) is expected for a clinic without that
      // capability -- hide the section rather than surfacing an error.
      setAuditEntries(null);
      return;
    }
    setAuditEntries((result.data as { entries: AuditEntry[] }).entries);
  }, []);

  useEffect(() => {
    if (ready) {
      load();
      loadAuditLog();
    }
  }, [ready, load, loadAuditLog]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    setSaved(false);
    setError(null);
    const result = await portalFetch("/api/portal/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    if (!result.ok) {
      setSaving(false);
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    // Settings-not-updating bug fix (Spec.md Section 0): the form used to
    // just flip a "Saved." flag and trust its own local (optimistic) state
    // as still-accurate -- but the backend can NORMALIZE a submitted value
    // (e.g. an emptied/garbled "Reminder offsets" field is coerced to a
    // default of "24", not stored as empty) without the page ever finding
    // out, so what was displayed after a save could silently diverge from
    // what was actually persisted. Re-fetching here (instead of trusting
    // the just-submitted `settings` object) makes the displayed values
    // always match the real stored ones.
    await load();
    setSaving(false);
    setSaved(true);
  }

  return (
    <PortalShell hospital={hospital} active="settings">
        <h1 className="text-display mb-space-5">Hospital settings</h1>

        {!settings ? (
          <p className="text-[13px] text-ink-400">Loading…</p>
        ) : (
          <form onSubmit={handleSave} className="flex max-w-2xl flex-col gap-space-5">
            <Card className="p-space-5">
              <h2 className="mb-space-3 text-[15px] font-bold text-ink-900">General</h2>
              <Field label="Hospital name" htmlFor="name" hint="Contact the platform team to change this — it's tied to your Meta WhatsApp connection.">
                <Input id="name" value={settings.name} disabled />
              </Field>
              <Field label="Welcome message text" htmlFor="welcome_message_text">
                <Textarea
                  id="welcome_message_text"
                  rows={2}
                  value={settings.welcome_message_text}
                  onChange={(e) => setSettings({ ...settings, welcome_message_text: e.target.value })}
                />
              </Field>
              <Field
                label="Reminder offsets (comma-separated hours)"
                htmlFor="reminder_offsets_hours"
                hint="e.g. 24,1 sends a reminder one day before and one hour before."
              >
                <Input
                  id="reminder_offsets_hours"
                  value={settings.reminder_offsets_hours}
                  onChange={(e) => setSettings({ ...settings, reminder_offsets_hours: e.target.value })}
                />
              </Field>
              <Field label="Reminder template name" htmlFor="reminder_template_name">
                <Input
                  id="reminder_template_name"
                  value={settings.reminder_template_name}
                  onChange={(e) => setSettings({ ...settings, reminder_template_name: e.target.value })}
                />
              </Field>
            </Card>

            <Card className="p-space-5">
              <h2 className="mb-space-1 text-[15px] font-bold text-ink-900">Closing message</h2>
              <p className="mb-space-3 text-[12.5px] text-ink-400">
                Appended after a booking is confirmed, a cancellation completes, or an appointment is rescheduled — the standard
                message is never replaced, this is added on afterward.
              </p>
              <Field label="Closing / thank-you message" htmlFor="closing_message_text" hint='e.g. "Thank you for choosing City Hospital. For emergencies, call 102."'>
                <Textarea
                  id="closing_message_text"
                  rows={2}
                  value={settings.closing_message_text}
                  onChange={(e) => setSettings({ ...settings, closing_message_text: e.target.value })}
                />
              </Field>
            </Card>

            <Card className="p-space-5">
              <h2 className="mb-space-1 text-[15px] font-bold text-ink-900">Business hours</h2>
              <p className="mb-space-3 text-[12.5px] text-ink-400">
                Shown as an extra line in the &quot;Hospital Information&quot; reply. Informational only — it doesn&apos;t change
                which slots doctors actually offer.
              </p>
              <Field label="Business hours" htmlFor="business_hours_text" hint="e.g. Mon-Sat, 9am-8pm">
                <Input
                  id="business_hours_text"
                  value={settings.business_hours_text}
                  onChange={(e) => setSettings({ ...settings, business_hours_text: e.target.value })}
                />
              </Field>
            </Card>

            <Card className="p-space-5">
              <h2 className="mb-space-1 text-[15px] font-bold text-ink-900">Language</h2>
              <p className="mb-space-3 text-[12.5px] text-ink-400">
                Which language a fresh conversation defaults to, and whether patients are asked to choose at all.
              </p>
              <Field label="Default language" htmlFor="default_language">
                <select
                  id="default_language"
                  value={settings.default_language}
                  onChange={(e) => setSettings({ ...settings, default_language: e.target.value as "en" | "hi" })}
                  className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13.5px] text-ink-900"
                >
                  <option value="en">English</option>
                  <option value="hi">हिन्दी (Hindi)</option>
                </select>
              </Field>
              <CheckboxRow
                checked={settings.language_prompt_enabled}
                onChange={(checked) => setSettings({ ...settings, language_prompt_enabled: checked })}
                className="mt-space-1"
              >
                Ask patients to choose a language at the start of every fresh conversation
              </CheckboxRow>
              {!settings.language_prompt_enabled && (
                <p className="mt-space-2 text-[12px] text-ink-400">
                  Patients will go straight to the menu in {settings.default_language === "hi" ? "हिन्दी" : "English"} — the
                  language picker won&apos;t be shown.
                </p>
              )}
            </Card>

            <Card className="p-space-5">
              <h2 className="mb-space-1 text-[15px] font-bold text-ink-900">Session timeout</h2>
              <p className="mb-space-3 text-[12.5px] text-ink-400">
                How long a patient can go quiet mid-conversation before the bot treats their next message as a fresh start.
              </p>
              <Field label="Timeout (minutes)" htmlFor="session_timeout_minutes" hint="Between 2 and 120 minutes.">
                <Input
                  id="session_timeout_minutes"
                  type="number"
                  min={2}
                  max={120}
                  value={settings.session_timeout_minutes}
                  onChange={(e) => setSettings({ ...settings, session_timeout_minutes: Number(e.target.value) })}
                />
              </Field>
            </Card>

            <Card className="p-space-5">
              <h2 className="mb-space-1 text-[15px] font-bold text-ink-900">Handoff auto-resolve</h2>
              <p className="mb-space-3 text-[12.5px] text-ink-400">
                An open &quot;Talk to Reception&quot; conversation with no new messages from either side for this long is
                automatically marked Resolved, instead of sitting open indefinitely.
              </p>
              <Field label="Auto-resolve after (hours)" htmlFor="handoff_auto_resolve_hours" hint="Between 1 and 168 hours (1 week).">
                <Input
                  id="handoff_auto_resolve_hours"
                  type="number"
                  min={1}
                  max={168}
                  value={settings.handoff_auto_resolve_hours}
                  onChange={(e) => setSettings({ ...settings, handoff_auto_resolve_hours: Number(e.target.value) })}
                />
              </Field>
            </Card>

            <Card className="p-space-5">
              <h2 className="mb-space-1 text-[15px] font-bold text-ink-900">Patient confirmation</h2>
              <p className="mb-space-3 text-[12.5px] text-ink-400">
                By default, a phone with exactly one linked patient skips straight to the menu -- zero extra taps. Turn this on to
                require an explicit &quot;Continue?&quot; confirmation even then.
              </p>
              <CheckboxRow
                checked={settings.require_patient_confirmation}
                onChange={(checked) => setSettings({ ...settings, require_patient_confirmation: checked })}
              >
                Require explicit confirmation before entering the menu, even for a single linked patient
              </CheckboxRow>
            </Card>

            <Card className="p-space-5">
              <h2 className="mb-space-1 text-[15px] font-bold text-ink-900">Privacy notice</h2>
              <p className="mb-space-3 text-[12.5px] text-ink-400">
                Shown on the &quot;Consent &amp; Privacy&quot; menu item, when enabled. Leave blank to show a generic default notice.
              </p>
              <Field label="Privacy notice text" htmlFor="privacy_notice_text">
                <Textarea
                  id="privacy_notice_text"
                  rows={4}
                  value={settings.privacy_notice_text}
                  onChange={(e) => setSettings({ ...settings, privacy_notice_text: e.target.value })}
                />
              </Field>
            </Card>

            {error && <p className="text-[12.5px] font-medium text-error">{error}</p>}
            {saved && <p className="text-[12.5px] font-medium text-success">Saved.</p>}

            <Button type="submit" disabled={saving} className="self-start">
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </form>
        )}

        {canManageAppointmentTypes && (
          <Card className="mt-space-5 max-w-2xl p-space-5">
            <h2 className="mb-space-1 text-[15px] font-bold text-ink-900">Appointment types</h2>
            <p className="mb-space-3 text-[12.5px] text-ink-400">
              Turn on/off which of your allowed appointment types show up in the WhatsApp booking menu.
              A type greyed out below hasn&apos;t been enabled for your account by the platform — contact
              support to request it.
            </p>
            <AppointmentTypeToggles canManage={canManageAppointmentTypes} />
          </Card>
        )}

        {canManageAppointmentTypes && (
          <Card className="mt-space-5 max-w-2xl p-space-5">
            <h2 className="mb-space-1 text-[15px] font-bold text-ink-900">Daycare stay durations</h2>
            <p className="mb-space-3 text-[12.5px] text-ink-400">
              The options a patient picks from when booking a Daycare appointment (only matters if
              Daycare is enabled for your account) -- e.g. a same-day few-hour stay vs. a multi-night
              admission. Add, relabel, deactivate, or remove your own options; deactivating one just
              hides it from new bookings, it doesn&apos;t change any appointment already booked with it.
            </p>
            <DaycareDurationOptions canManage={canManageAppointmentTypes} />
          </Card>
        )}

        {auditEntries && auditEntries.length > 0 && (
          <Card className="mt-space-5 max-w-2xl p-space-5">
            <h2 className="mb-space-1 text-[15px] font-bold text-ink-900">Activity log</h2>
            <p className="mb-space-3 text-[12.5px] text-ink-400">
              Recent changes made by your staff through this portal -- doctor/department edits, feature toggles,
              settings updates. Platform-level changes (made by the operator on your behalf) aren&apos;t shown here.
            </p>
            <ul className="divide-y divide-line">
              {auditEntries.map((entry) => (
                <li key={entry.id} className="py-space-2 text-[12.5px]">
                  <div className="flex items-center justify-between gap-space-3">
                    <span className="font-medium text-ink-900">{entry.action}</span>
                    <span className="shrink-0 text-ink-400">{entry.created_at}</span>
                  </div>
                  {formatAuditChanges(entry) && <p className="mt-space-1 text-ink-600">{formatAuditChanges(entry)}</p>}
                </li>
              ))}
            </ul>
          </Card>
        )}
    </PortalShell>
  );
}
