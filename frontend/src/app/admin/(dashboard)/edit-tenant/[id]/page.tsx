"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CheckboxRow } from "@/components/ui/Checkbox";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { adminFetch } from "@/lib/adminAuth";

type TenantDetail = {
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

type AppointmentTypeRow = {
  id: string;
  label: string;
  is_active: boolean;
  is_allowed: boolean;
};

type FormState = {
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

function capabilitiesMatch(a: string[], b: string[]): boolean {
  const sortedA = [...a].sort();
  const sortedB = [...b].sort();
  return sortedA.length === sortedB.length && sortedA.every((v, i) => v === sortedB[i]);
}

function titleCaseCapability(key: string): string {
  return key
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function EditTenantForm({ tenantId }: { tenantId: number }) {
  const [tenant, setTenant] = useState<TenantDetail | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

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

  function toggleFeature(key: string, checked: boolean) {
    if (!form) return;
    setForm({
      ...form,
      enabled_features: checked
        ? [...form.enabled_features, key]
        : form.enabled_features.filter((k) => k !== key),
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

  const [appointmentTypeError, setAppointmentTypeError] = useState<string | null>(null);

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
        : prev
    );
  }

  useEffect(() => {
    load();
  }, [load]);

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

  return (
    <div className="mx-auto max-w-[720px] px-space-4 py-space-7 md:px-space-7">
      <Link href="/admin/tenants" className="mb-space-4 inline-block text-[13px] font-semibold text-brand-600 hover:underline">
        ← All tenants
      </Link>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      {!tenant || !form ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : (
        <Card className="p-space-5">
          <p className="text-eyebrow mb-space-1">Editing tenant #{tenant.id}</p>
          <h1 className="text-display mb-space-4">{tenant.name}</h1>
          <p className="text-body mb-space-5">Only fields you change are updated — leave the token/secret fields blank to keep their current values.</p>

          <form onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
              <Field label="Hospital name" htmlFor="name" required>
                <Input id="name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </Field>
              <Field label="WhatsApp phone_number_id" htmlFor="phone_id" required>
                <Input
                  id="phone_id"
                  required
                  value={form.whatsapp_phone_number_id}
                  onChange={(e) => setForm({ ...form, whatsapp_phone_number_id: e.target.value })}
                />
              </Field>
              <Field label="Access token" htmlFor="access_token" hint={`Leave blank to keep current (${tenant.access_token_masked})`}>
                <Input id="access_token" value={form.access_token} onChange={(e) => setForm({ ...form, access_token: e.target.value })} />
              </Field>
              <Field label="App secret" htmlFor="app_secret" hint={`Leave blank to keep current (${tenant.app_secret_masked})`}>
                <Input id="app_secret" value={form.app_secret} onChange={(e) => setForm({ ...form, app_secret: e.target.value })} />
              </Field>
            </div>

            <Field label="Welcome message text" htmlFor="welcome_message_text">
              <Textarea
                id="welcome_message_text"
                rows={2}
                value={form.welcome_message_text}
                onChange={(e) => setForm({ ...form, welcome_message_text: e.target.value })}
              />
            </Field>

            <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
              <Field label="Reminder offsets (hours)" htmlFor="reminder_offsets_hours">
                <Input
                  id="reminder_offsets_hours"
                  value={form.reminder_offsets_hours}
                  onChange={(e) => setForm({ ...form, reminder_offsets_hours: e.target.value })}
                />
              </Field>
              <Field label="Reminder template name" htmlFor="reminder_template_name">
                <Input
                  id="reminder_template_name"
                  value={form.reminder_template_name}
                  onChange={(e) => setForm({ ...form, reminder_template_name: e.target.value })}
                />
              </Field>
            </div>

            <Field
              label="Bookings portal password"
              htmlFor="portal_password"
              hint={tenant.has_portal_password ? "Leave blank to keep the current password." : "Not set yet — set one so staff can log in."}
            >
              <Input id="portal_password" type="password" value={form.portal_password} onChange={(e) => setForm({ ...form, portal_password: e.target.value })} />
            </Field>

            <Field label="Tenant type" htmlFor="tenant_type">
              <select
                id="tenant_type"
                value={form.tenant_type}
                onChange={(e) => setForm({ ...form, tenant_type: e.target.value })}
                className="h-11 w-full rounded-md border border-line bg-card px-space-3 text-[14px] text-ink-900"
              >
                <option value="hospital">Hospital</option>
                <option value="clinic">Clinic</option>
              </select>
            </Field>

            <Field
              label="Admin capabilities"
              htmlFor="admin_capabilities"
              hint="Controls which staff-portal management screens this tenant can use. Changing tenant type above does NOT change these automatically — use Reset to defaults if you want them to match."
            >
              <div className="mb-space-2 flex items-center gap-space-2">
                <Button type="button" variant="secondary" onClick={resetCapabilitiesToDefaults}>
                  Reset to {form.tenant_type} defaults
                </Button>
                {!capabilitiesMatch(form.admin_capabilities, tenant.default_capabilities_by_type[form.tenant_type] ?? []) && (
                  <span className="text-[13px] text-error">
                    Custom — doesn&apos;t match the {form.tenant_type} default set.
                  </span>
                )}
              </div>
              <div id="admin_capabilities" className="grid grid-cols-1 gap-space-1 sm:grid-cols-2">
                {tenant.all_capabilities.map((key) => (
                  <CheckboxRow
                    key={key}
                    checked={form.admin_capabilities.includes(key)}
                    onChange={(checked) => toggleCapability(key, checked)}
                  >
                    {titleCaseCapability(key)}
                  </CheckboxRow>
                ))}
              </div>
            </Field>

            <Field
              label="Appointment types"
              htmlFor="appointment_types"
              hint="Which types this tenant may offer at all. Unchecking one also turns it off in the tenant's own portal immediately — the tenant can then only switch it back on if you re-allow it here first."
            >
              {appointmentTypeError && <p className="mb-space-2 text-[12.5px] text-error">{appointmentTypeError}</p>}
              <div id="appointment_types" className="grid grid-cols-1 gap-space-1 sm:grid-cols-2">
                {tenant.appointment_types.map((at) => (
                  <CheckboxRow
                    key={at.id}
                    checked={at.is_allowed}
                    onChange={(checked) => toggleAppointmentTypeAllowed(at.id, checked)}
                  >
                    {at.label}
                  </CheckboxRow>
                ))}
              </div>
            </Field>

            <Field label="Data connection tier" htmlFor="data_tier">
              <select
                id="data_tier"
                value={form.data_tier}
                onChange={(e) => setForm({ ...form, data_tier: e.target.value })}
                className="h-11 w-full rounded-md border border-line bg-card px-space-3 text-[14px] text-ink-900"
              >
                <option value="tier1">Tier 1 — this platform</option>
                <option value="tier2">Tier 2 — external API</option>
                <option value="tier3">Tier 3 — direct database</option>
              </select>
            </Field>

            <Field
              label="Enabled WhatsApp features"
              htmlFor="enabled_features"
              hint="Only set once, at onboarding -- this is the one place to change it afterward. A hospital's own /portal/settings can rename a label for an already-enabled feature, but can't turn one on or off."
            >
              <div id="enabled_features" className="grid grid-cols-1 gap-space-1 sm:grid-cols-2">
                {Object.entries(tenant.feature_default_labels).map(([key, label]) => (
                  <CheckboxRow
                    key={key}
                    checked={form.enabled_features.includes(key)}
                    onChange={(checked) => toggleFeature(key, checked)}
                  >
                    {label}
                  </CheckboxRow>
                ))}
              </div>
            </Field>

            {form.data_tier === "tier2" && (
              <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
                <Field label="API base URL" htmlFor="api_base_url" required>
                  <Input id="api_base_url" required value={form.api_base_url} onChange={(e) => setForm({ ...form, api_base_url: e.target.value })} />
                </Field>
                <Field label="API key" htmlFor="api_key" required>
                  <Input id="api_key" required value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
                </Field>
              </div>
            )}

            {errors.length > 0 && (
              <div className="mb-space-3 rounded-md border border-error bg-error-tint p-space-3 text-[12.5px] text-error">
                <ul className="list-disc pl-space-4">
                  {errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </div>
            )}
            {saved && <p className="mb-space-3 text-[12.5px] font-medium text-success">Saved.</p>}

            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </form>
        </Card>
      )}

    </div>
  );
}

export default function EditTenantPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <EditTenantForm tenantId={Number(id)} />;
}
