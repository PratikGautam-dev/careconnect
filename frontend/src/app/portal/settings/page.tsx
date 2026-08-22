"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CheckboxRow } from "@/components/ui/Checkbox";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
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
  feature_labels: Record<string, string>;
  feature_default_labels: Record<string, string>;
  closing_message_text: string;
  business_hours_text: string;
  default_language: "en" | "hi";
  language_prompt_enabled: boolean;
  session_timeout_minutes: number;
};

const FEATURE_DISPLAY_NAMES: Record<string, string> = {
  booking: "Book Appointment",
  reschedule: "Reschedule Appointment",
  cancel: "Cancel Appointment",
  view_appointments: "My Appointments",
  hospital_info: "Hospital Information",
  reception_handoff: "Talk to Reception",
  faq: "FAQ / Information",
};

export default function PortalSettingsPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    const result = await portalFetch("/api/portal/settings");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setSettings(result.data as Settings);
  }, [router]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

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
    setSaving(false);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setSaved(true);
  }

  function setFeatureLabel(key: string, label: string) {
    if (!settings) return;
    setSettings({ ...settings, feature_labels: { ...settings.feature_labels, [key]: label } });
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
              <h2 className="mb-space-1 text-[15px] font-bold text-ink-900">Menu labels</h2>
              <p className="mb-space-3 text-[12.5px] text-ink-400">
                Rename how an enabled feature appears in your WhatsApp menu. Leave a field blank to use the default.
              </p>
              {settings.enabled_features.length === 0 ? (
                <p className="text-[13px] text-ink-400">No features are enabled yet — enable some via onboarding/tenant setup first.</p>
              ) : (
                settings.enabled_features.map((key) => (
                  <Field key={key} label={FEATURE_DISPLAY_NAMES[key] || key} htmlFor={`label_${key}`}>
                    <Input
                      id={`label_${key}`}
                      placeholder={settings.feature_default_labels[key] || ""}
                      value={settings.feature_labels[key] || ""}
                      onChange={(e) => setFeatureLabel(key, e.target.value)}
                    />
                  </Field>
                ))
              )}
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

            {error && <p className="text-[12.5px] font-medium text-error">{error}</p>}
            {saved && <p className="text-[12.5px] font-medium text-success">Saved.</p>}

            <Button type="submit" disabled={saving} className="self-start">
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </form>
        )}
    </PortalShell>
  );
}
