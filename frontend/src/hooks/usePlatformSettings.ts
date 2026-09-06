import { useCallback, useEffect, useState } from "react";
import { adminFetch } from "@/lib/adminAuth";
import { toast } from "@/lib/toast";

export type PlatformSettings = {
  max_active_patient_links: number;
  // Migration 0014: moved off hospitals.feature_labels/dpdp_consent_required
  // -- ONE value applied to every hospital's WhatsApp bot now, not a
  // per-tenant self-serve setting (frontend/src/app/portal/settings/page.tsx
  // no longer has these two sections).
  feature_labels: Record<string, string>;
  feature_default_labels: Record<string, string>;
  dpdp_consent_required: boolean;
};

/** Loads + saves the /admin/platform-settings form -- global values applied
 * identically across every hospital (no per-tenant override). */
export function usePlatformSettings() {
  const [settings, setSettings] = useState<PlatformSettings | null>(null);
  const [maxActiveLinks, setMaxActiveLinks] = useState("");
  const [featureLabels, setFeatureLabels] = useState<Record<string, string>>({});
  const [dpdpRequired, setDpdpRequired] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const result = await adminFetch("/api/admin/platform-settings");
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — refresh to sign in again." : result.error);
      return;
    }
    const data = result.data as PlatformSettings;
    setSettings(data);
    setMaxActiveLinks(String(data.max_active_patient_links));
    setFeatureLabels(data.feature_labels);
    setDpdpRequired(data.dpdp_consent_required);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function setFeatureLabel(key: string, label: string) {
    setFeatureLabels((prev) => ({ ...prev, [key]: label }));
    setSaved(false);
  }

  function updateMaxActiveLinks(value: string) {
    setMaxActiveLinks(value);
    setSaved(false);
  }

  function updateDpdpRequired(checked: boolean) {
    setDpdpRequired(checked);
    setSaved(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    setSaving(true);
    try {
      const result = await adminFetch("/api/admin/platform-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_active_patient_links: Number(maxActiveLinks),
          feature_labels: featureLabels,
          dpdp_consent_required: dpdpRequired,
        }),
      });
      if (!result.ok) {
        setError(result.unauthorized ? "Session expired — refresh to sign in again." : result.error);
        if (!result.unauthorized) toast.error("Couldn't save platform settings", result.error);
        return;
      }
      const data = result.data as PlatformSettings;
      setSettings(data);
      setFeatureLabels(data.feature_labels);
      setDpdpRequired(data.dpdp_consent_required);
      setSaved(true);
      toast.success("Platform settings saved");
    } finally {
      setSaving(false);
    }
  }

  return {
    settings,
    maxActiveLinks,
    setMaxActiveLinks: updateMaxActiveLinks,
    featureLabels,
    setFeatureLabel,
    dpdpRequired,
    setDpdpRequired: updateDpdpRequired,
    error,
    saved,
    saving,
    handleSubmit,
  };
}
