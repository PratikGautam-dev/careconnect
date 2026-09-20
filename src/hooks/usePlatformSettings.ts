import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";
import { toast } from "@/lib/toast";

export type PlatformSettings = {
  max_active_patient_links: number;
  // One value applied to every hospital's WhatsApp bot, not a per-tenant setting.
  feature_labels: Record<string, string>;
  feature_default_labels: Record<string, string>;
  dpdp_consent_required: boolean;
};

/** Loads + saves the /admin/platform-settings form -- global values applied
 * identically across every hospital (no per-tenant override). */
export function usePlatformSettings() {
  const { data: settings, error: queryError } = useQuery({
    queryKey: ["admin-platform-settings"],
    retry: false,
    queryFn: async () => {
      const result = await adminFetch("/api/admin/platform-settings");
      return unwrapAdminResult<PlatformSettings>(result);
    },
  });

  // Editable draft, seeded once per successful load.
  const [seeded, setSeeded] = useState(false);
  const [maxActiveLinks, setMaxActiveLinksRaw] = useState("");
  const [featureLabels, setFeatureLabels] = useState<Record<string, string>>({});
  const [dpdpRequired, setDpdpRequiredRaw] = useState(false);
  if (settings && !seeded) {
    setSeeded(true);
    setMaxActiveLinksRaw(String(settings.max_active_patient_links));
    setFeatureLabels(settings.feature_labels);
    setDpdpRequiredRaw(settings.dpdp_consent_required);
  }

  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  function setFeatureLabel(key: string, label: string) {
    setFeatureLabels((prev) => ({ ...prev, [key]: label }));
    setSaved(false);
  }

  function updateMaxActiveLinks(value: string) {
    setMaxActiveLinksRaw(value);
    setSaved(false);
  }

  function updateDpdpRequired(checked: boolean) {
    setDpdpRequiredRaw(checked);
    setSaved(false);
  }

  const saveMutation = useMutation({
    mutationFn: async (payload: {
      max_active_patient_links: number;
      feature_labels: Record<string, string>;
      dpdp_consent_required: boolean;
    }) => {
      const result = await adminFetch("/api/admin/platform-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapAdminResult<PlatformSettings>(result);
    },
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaveError(null);
    setSaved(false);
    try {
      const data = await saveMutation.mutateAsync({
        max_active_patient_links: Number(maxActiveLinks),
        feature_labels: featureLabels,
        dpdp_consent_required: dpdpRequired,
      });
      setFeatureLabels(data.feature_labels);
      setDpdpRequiredRaw(data.dpdp_consent_required);
      setSaved(true);
      toast.success("Platform settings saved");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setSaveError(message);
      toast.error("Couldn't save platform settings", message);
    }
  }

  return {
    settings: settings ?? null,
    maxActiveLinks,
    setMaxActiveLinks: updateMaxActiveLinks,
    featureLabels,
    setFeatureLabel,
    dpdpRequired,
    setDpdpRequired: updateDpdpRequired,
    error: saveError ?? (queryError ? (queryError as Error).message : null),
    saved,
    saving: saveMutation.isPending,
    handleSubmit,
  };
}
