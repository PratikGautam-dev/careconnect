import { useCallback, useEffect, useState } from "react";
import { adminFetch } from "@/lib/adminAuth";

export type TenantDetail = {
  id: number;
  name: string;
  whatsapp_phone_number_id: string;
  access_token_masked: string;
  app_secret_masked: string;
  welcome_message_text: string;
  reminder_offsets_hours: string;
  reminder_template_name: string;
  data_tier: string;
  external_api_base_url: string;
  external_api_key: string;
  has_portal_password: boolean;
  is_active: boolean;
  enabled_features: string[];
  feature_default_labels: Record<string, string>;
  tenant_type: string;
  admin_capabilities: string[];
  all_capabilities: string[];
  default_capabilities_by_type: Record<string, string[]>;
  appointment_types: AppointmentTypeRow[];
};

export type AppointmentTypeRow = {
  id: string;
  label: string;
  is_active: boolean;
  is_allowed: boolean;
};

export type TenantFormState = {
  name: string;
  whatsapp_phone_number_id: string;
  access_token: string;
  app_secret: string;
  welcome_message_text: string;
  reminder_offsets_hours: string;
  reminder_template_name: string;
  portal_password: string;
  data_tier: string;
  api_base_url: string;
  api_key: string;
  enabled_features: string[];
  tenant_type: string;
  admin_capabilities: string[];
};

/** Loads + saves one tenant for the /admin/tenants/[id] edit form, and owns
 * the appointment-type allow-list toggle (its own independent save, not
 * part of the main form submit). */
export function useEditTenant(tenantId: number) {
  const [tenant, setTenant] = useState<TenantDetail | null>(null);
  const [form, setForm] = useState<TenantFormState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [appointmentTypeError, setAppointmentTypeError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await adminFetch(`/api/admin/tenants/${tenantId}`);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — refresh to sign in again." : result.error);
      return;
    }
    const t = (result.data as { tenant: TenantDetail }).tenant;
    setTenant(t);
    setForm({
      name: t.name,
      whatsapp_phone_number_id: t.whatsapp_phone_number_id,
      access_token: "",
      app_secret: "",
      welcome_message_text: t.welcome_message_text,
      reminder_offsets_hours: t.reminder_offsets_hours,
      reminder_template_name: t.reminder_template_name,
      portal_password: "",
      data_tier: t.data_tier,
      api_base_url: t.external_api_base_url,
      api_key: t.external_api_key,
      enabled_features: t.enabled_features,
      tenant_type: t.tenant_type,
      admin_capabilities: t.admin_capabilities,
    });
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  function toggleFeature(key: string, checked: boolean) {
    if (!form) return;
    setForm({
      ...form,
      enabled_features: checked ? [...form.enabled_features, key] : form.enabled_features.filter((k) => k !== key),
    });
  }

  function resetCapabilitiesToDefaults() {
    if (!form || !tenant) return;
    const defaults = tenant.default_capabilities_by_type[form.tenant_type] ?? [];
    setForm({ ...form, admin_capabilities: defaults });
  }

  function toggleCapability(key: string, checked: boolean) {
    if (!form) return;
    setForm({
      ...form,
      admin_capabilities: checked
        ? [...form.admin_capabilities, key]
        : form.admin_capabilities.filter((k) => k !== key),
    });
  }

  async function toggleAppointmentTypeAllowed(appointmentTypeId: string, isAllowed: boolean) {
    setAppointmentTypeError(null);
    const result = await adminFetch(`/api/admin/tenants/${tenantId}/appointment-types/${appointmentTypeId}/allowed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_allowed: isAllowed }),
    });
    if (!result.ok) {
      setAppointmentTypeError(result.unauthorized ? "Session expired — refresh to sign in again." : result.error);
      return;
    }
    const updated = (result.data as { appointment_type: AppointmentTypeRow }).appointment_type;
    setTenant((prev) =>
      prev
        ? { ...prev, appointment_types: prev.appointment_types.map((t) => (t.id === updated.id ? updated : t)) }
        : prev,
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setSaving(true);
    setSaved(false);
    setErrors([]);
    const result = await adminFetch(`/api/admin/tenants/${tenantId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    setSaving(false);
    if (!result.ok) {
      if (result.unauthorized) setError("Session expired — refresh to sign in again.");
      else setErrors([result.error]);
      return;
    }
    const data = result.data as { tenant?: TenantDetail; errors?: string[] };
    if (data.errors?.length) {
      setErrors(data.errors);
      return;
    }
    setSaved(true);
    load();
  }

  return {
    tenant,
    form,
    setForm,
    error,
    errors,
    saving,
    saved,
    appointmentTypeError,
    toggleFeature,
    resetCapabilitiesToDefaults,
    toggleCapability,
    toggleAppointmentTypeAllowed,
    handleSubmit,
  };
}
