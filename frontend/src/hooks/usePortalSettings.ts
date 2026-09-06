import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

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

  // docs/per-appointment-type-flow-plan.md Phase 2 Step 2 follow-up: fees are
  // "" (unset -- no fee line shown) or a numeric string, since a plain
  // `number` type can't represent "no value entered" as distinct from 0.
  followup_validity_days: number;
  followup_fee: number | "";
  new_consultation_fee: number | "";
  // Lab Test Phase 2 follow-up: flat fee added to a home-collection Lab Test
  // booking's price review, same "" (unset) convention as the two fees above.
  home_collection_charge: number | "";
};

/** Loads + saves the /portal/settings form. */
export function usePortalSettings(ready: boolean) {
  const router = useRouter();
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
    // followup_fee/new_consultation_fee come back as `null` when unset (no
    // default to fall back to, unlike e.g. session_timeout_minutes) --
    // coerced to "" here so the numeric <Input> below never renders "null".
    const data = result.data as Settings & {
      followup_fee: number | null; new_consultation_fee: number | null; home_collection_charge: number | null;
    };
    setSettings({
      ...data, followup_fee: data.followup_fee ?? "", new_consultation_fee: data.new_consultation_fee ?? "",
      home_collection_charge: data.home_collection_charge ?? "",
    });
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
    if (!result.ok) {
      setSaving(false);
      if (result.unauthorized) router.push("/portal/login");
      else {
        setError(result.error);
        toast.error("Couldn't save settings", result.error);
      }
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
    toast.success("Settings saved");
  }

  return { settings, setSettings, error, saving, saved, handleSave };
}
