"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { PortalSidebar } from "@/components/portal/PortalSidebar";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { portalFetch } from "@/lib/portalAuth";

type Settings = {
  name: string;
  welcome_message_text: string;
  reminder_offsets_hours: string;
  reminder_template_name: string;
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

  return (
    <div className="flex h-screen overflow-hidden bg-paper">
      <PortalSidebar hospital={hospital} active="settings" />
      <main className="flex-1 overflow-y-auto p-space-6">
        <h1 className="text-display mb-space-5">Hospital settings</h1>

        <Card className="max-w-xl p-space-5">
          {!settings ? (
            <p className="text-[13px] text-ink-400">Loading…</p>
          ) : (
            <form onSubmit={handleSave}>
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

              {error && <p className="mb-space-3 text-[12.5px] font-medium text-error">{error}</p>}
              {saved && <p className="mb-space-3 text-[12.5px] font-medium text-success">Saved.</p>}

              <Button type="submit" disabled={saving}>
                {saving ? "Saving…" : "Save changes"}
              </Button>
            </form>
          )}
        </Card>
      </main>
    </div>
  );
}
