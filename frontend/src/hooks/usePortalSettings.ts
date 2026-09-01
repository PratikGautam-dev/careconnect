import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalFetch } from "@/lib/portalAuth";

export type Settings = {
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
  // CareConnect architecture doc alignment (Spec.md Section 0).
  require_patient_confirmation: boolean;
  privacy_notice_text: string;

  handoff_auto_resolve_hours: number;
  
};

export type AuditEntry = {
  id: number;
  actor_level: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  before_value: Record<string, unknown> | null;
  after_value: Record<string, unknown> | null;
  created_at: string;
};

/** Loads + saves the /portal/settings form, plus this hospital's own
 * (capability-gated) activity log. */
export function usePortalSettings(ready: boolean) {
  const router = useRouter();
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

  return { settings, setSettings, error, saving, saved, auditEntries, handleSave };
}
