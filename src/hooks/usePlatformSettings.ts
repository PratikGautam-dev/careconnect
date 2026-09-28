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
  // How long audit_logs rows are kept before an external cron
  // (POST /internal/purge-audit-logs) deletes them. 30-730 days.
  audit_log_retention_days: number;
  // Charged on top of every payable appointment fee (flows/booking/book.py)
  // -- the default rate for every tenant (a hospital with its own Razorpay
  // account can override it, admin/tenants/[id] page). *_enabled is the
  // real on/off switch; percent is kept even while disabled so re-enabling
  // doesn't lose the last-configured rate.
  gst_enabled: boolean;
  gst_percent: number | null;
  platform_fee_enabled: boolean;
  platform_fee_percent: number | null;
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
  const [auditLogRetentionDays, setAuditLogRetentionDaysRaw] = useState("180");
  // "" (unset) means 0% -- same convention usePortalSettings' own fee
  // fields use, not a numeric default that would misrepresent "never
  // configured" as an actual chosen rate.
  const [gstEnabled, setGstEnabledRaw] = useState(false);
  const [gstPercent, setGstPercentRaw] = useState("");
  const [platformFeeEnabled, setPlatformFeeEnabledRaw] = useState(false);
  const [platformFeePercent, setPlatformFeePercentRaw] = useState("");
  if (settings && !seeded) {
    setSeeded(true);
    setMaxActiveLinksRaw(String(settings.max_active_patient_links));
    setFeatureLabels(settings.feature_labels);
    setDpdpRequiredRaw(settings.dpdp_consent_required);
    setAuditLogRetentionDaysRaw(String(settings.audit_log_retention_days));
    setGstEnabledRaw(settings.gst_enabled);
    setGstPercentRaw(settings.gst_percent != null ? String(settings.gst_percent) : "");
    setPlatformFeeEnabledRaw(settings.platform_fee_enabled);
    setPlatformFeePercentRaw(
      settings.platform_fee_percent != null ? String(settings.platform_fee_percent) : "",
    );
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

  function updateAuditLogRetentionDays(value: string) {
    setAuditLogRetentionDaysRaw(value);
    setSaved(false);
  }

  function updateGstEnabled(checked: boolean) {
    setGstEnabledRaw(checked);
    setSaved(false);
  }

  function updateGstPercent(value: string) {
    setGstPercentRaw(value);
    setSaved(false);
  }

  function updatePlatformFeeEnabled(checked: boolean) {
    setPlatformFeeEnabledRaw(checked);
    setSaved(false);
  }

  function updatePlatformFeePercent(value: string) {
    setPlatformFeePercentRaw(value);
    setSaved(false);
  }

  const saveMutation = useMutation({
    mutationFn: async (payload: {
      max_active_patient_links: number;
      feature_labels: Record<string, string>;
      dpdp_consent_required: boolean;
      audit_log_retention_days: number;
      gst_enabled: boolean;
      gst_percent: number | null;
      platform_fee_enabled: boolean;
      platform_fee_percent: number | null;
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
        audit_log_retention_days: Number(auditLogRetentionDays),
        gst_enabled: gstEnabled,
        gst_percent: gstPercent === "" ? null : Number(gstPercent),
        platform_fee_enabled: platformFeeEnabled,
        platform_fee_percent: platformFeePercent === "" ? null : Number(platformFeePercent),
      });
      setFeatureLabels(data.feature_labels);
      setDpdpRequiredRaw(data.dpdp_consent_required);
      setAuditLogRetentionDaysRaw(String(data.audit_log_retention_days));
      setGstEnabledRaw(data.gst_enabled);
      setGstPercentRaw(data.gst_percent != null ? String(data.gst_percent) : "");
      setPlatformFeeEnabledRaw(data.platform_fee_enabled);
      setPlatformFeePercentRaw(
        data.platform_fee_percent != null ? String(data.platform_fee_percent) : "",
      );
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
    auditLogRetentionDays,
    setAuditLogRetentionDays: updateAuditLogRetentionDays,
    gstEnabled,
    setGstEnabled: updateGstEnabled,
    gstPercent,
    setGstPercent: updateGstPercent,
    platformFeeEnabled,
    setPlatformFeeEnabled: updatePlatformFeeEnabled,
    platformFeePercent,
    setPlatformFeePercent: updatePlatformFeePercent,
    error: saveError ?? (queryError ? (queryError as Error).message : null),
    saved,
    saving: saveMutation.isPending,
    handleSubmit,
  };
}
