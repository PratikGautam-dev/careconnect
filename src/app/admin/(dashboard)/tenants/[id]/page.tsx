"use client";

import { use } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CheckboxRow } from "@/components/ui/Checkbox";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { Switch } from "@/components/ui/Switch";
import { useEditTenant } from "@/hooks/useEditTenant";

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
  const {
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
    paymentSettings,
    paymentForm,
    setPaymentForm,
    paymentSettingsError,
    paymentSettingsErrors,
    savingPaymentSettings,
    paymentSettingsSaved,
    handlePaymentSettingsSubmit,
  } = useEditTenant(tenantId);

  return (
    <div>
      <Link
        href="/admin/tenants"
        className="mb-space-4 text-brand-600 inline-block text-[13px] font-semibold hover:underline"
      >
        ← All tenants
      </Link>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      {!tenant || !form ? (
        <p className="text-ink-400 text-[13px]">Loading…</p>
      ) : (
        <>
          <Card className="p-space-5">
            <p className="text-eyebrow mb-space-1">Editing tenant #{tenant.id}</p>
            <h1 className="text-display mb-space-4">{tenant.name}</h1>
            <p className="text-body mb-space-5">
              Only fields you change are updated — leave the token/secret fields blank to keep their
              current values.
            </p>

            <form onSubmit={handleSubmit}>
              <div className="gap-x-space-4 grid grid-cols-1 md:grid-cols-2">
                <Field label="Hospital name" htmlFor="name" required>
                  <Input
                    id="name"
                    required
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                  />
                </Field>
                <Field label="WhatsApp phone_number_id" htmlFor="phone_id" required>
                  <Input
                    id="phone_id"
                    required
                    value={form.whatsapp_phone_number_id}
                    onChange={(e) => setForm({ ...form, whatsapp_phone_number_id: e.target.value })}
                  />
                </Field>
                <Field
                  label="Access token"
                  htmlFor="access_token"
                  hint={`Leave blank to keep current (${tenant.access_token_masked})`}
                >
                  <Input
                    id="access_token"
                    value={form.access_token}
                    onChange={(e) => setForm({ ...form, access_token: e.target.value })}
                  />
                </Field>
                <Field
                  label="App secret"
                  htmlFor="app_secret"
                  hint={`Leave blank to keep current (${tenant.app_secret_masked})`}
                >
                  <Input
                    id="app_secret"
                    value={form.app_secret}
                    onChange={(e) => setForm({ ...form, app_secret: e.target.value })}
                  />
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

              <div className="gap-x-space-4 grid grid-cols-1 md:grid-cols-2">
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
                hint={
                  tenant.has_portal_password
                    ? "Leave blank to keep the current password."
                    : "Not set yet — set one so staff can log in."
                }
              >
                <Input
                  id="portal_password"
                  type="password"
                  value={form.portal_password}
                  onChange={(e) => setForm({ ...form, portal_password: e.target.value })}
                />
              </Field>

              <Field label="Tenant type" htmlFor="tenant_type">
                <select
                  id="tenant_type"
                  value={form.tenant_type}
                  onChange={(e) => setForm({ ...form, tenant_type: e.target.value })}
                  className="border-line bg-card px-space-3 text-ink-900 h-11 w-full rounded-md border text-[14px]"
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
                <div className="mb-space-2 gap-space-2 flex items-center">
                  <Button type="button" variant="secondary" onClick={resetCapabilitiesToDefaults}>
                    Reset to {form.tenant_type} defaults
                  </Button>
                  {!capabilitiesMatch(
                    form.admin_capabilities,
                    tenant.default_capabilities_by_type[form.tenant_type] ?? [],
                  ) && (
                    <span className="text-error text-[13px]">
                      Custom — doesn&apos;t match the {form.tenant_type} default set.
                    </span>
                  )}
                </div>
                <div
                  id="admin_capabilities"
                  className="gap-space-1 grid grid-cols-1 md:grid-cols-2"
                >
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
                {appointmentTypeError && (
                  <p className="mb-space-2 text-error text-[12.5px]">{appointmentTypeError}</p>
                )}
                <div id="appointment_types" className="gap-space-1 grid grid-cols-1 md:grid-cols-2">
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
                  className="border-line bg-card px-space-3 text-ink-900 h-11 w-full rounded-md border text-[14px]"
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
                <div id="enabled_features" className="gap-space-1 grid grid-cols-1 md:grid-cols-2">
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
                <div className="gap-x-space-4 grid grid-cols-1 md:grid-cols-2">
                  <Field label="API base URL" htmlFor="api_base_url" required>
                    <Input
                      id="api_base_url"
                      required
                      value={form.api_base_url}
                      onChange={(e) => setForm({ ...form, api_base_url: e.target.value })}
                    />
                  </Field>
                  <Field label="API key" htmlFor="api_key" required>
                    <Input
                      id="api_key"
                      required
                      value={form.api_key}
                      onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                    />
                  </Field>
                </div>
              )}

              {errors.length > 0 && (
                <div className="mb-space-3 border-error bg-error-tint p-space-3 text-error rounded-md border text-[12.5px]">
                  <ul className="pl-space-4 list-disc">
                    {errors.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                </div>
              )}
              {saved && <p className="mb-space-3 text-success text-[12.5px] font-medium">Saved.</p>}

              <Button type="submit" disabled={saving}>
                {saving ? "Saving…" : "Save changes"}
              </Button>
            </form>
          </Card>

          {paymentForm && (
            <Card className="p-space-5 mt-space-4">
              <p className="text-eyebrow mb-space-1">Payment gateway</p>
              <h2 className="text-display mb-space-2 text-[18px]">Razorpay routing</h2>
              <p className="text-body mb-space-4">
                Whether this tenant&apos;s patient-facing payments run through the platform&apos;s
                own Razorpay account or the tenant&apos;s own. Super-admin only — the tenant&apos;s
                own portal cannot see or change this.
              </p>
              {paymentSettingsError && (
                <p className="mb-space-4 text-error text-[13px]">{paymentSettingsError}</p>
              )}

              <form onSubmit={handlePaymentSettingsSubmit}>
                <div className="mb-space-4 gap-space-3 flex items-center">
                  <Switch
                    checked={paymentForm.payment_mode === "hospital_own"}
                    onChange={() =>
                      setPaymentForm({
                        ...paymentForm,
                        payment_mode:
                          paymentForm.payment_mode === "hospital_own" ? "platform" : "hospital_own",
                      })
                    }
                    aria-label="Use this tenant's own Razorpay account"
                  />
                  <span className="text-[14px] font-medium">
                    {paymentForm.payment_mode === "hospital_own"
                      ? "Using the tenant's own Razorpay account"
                      : "Using the platform's Razorpay account (default)"}
                  </span>
                </div>

                {paymentForm.payment_mode === "hospital_own" && (
                  <div className="gap-x-space-4 grid grid-cols-1 md:grid-cols-2">
                    <Field label="Razorpay key ID" htmlFor="razorpay_key_id">
                      <Input
                        id="razorpay_key_id"
                        value={paymentForm.razorpay_key_id}
                        onChange={(e) =>
                          setPaymentForm({ ...paymentForm, razorpay_key_id: e.target.value })
                        }
                      />
                    </Field>
                    <div />
                    <Field
                      label="Razorpay key secret"
                      htmlFor="razorpay_key_secret"
                      hint={
                        paymentSettings?.key_secret_configured
                          ? "Leave blank to keep the current secret."
                          : "Not set yet."
                      }
                    >
                      <PasswordInput
                        id="razorpay_key_secret"
                        value={paymentForm.razorpay_key_secret}
                        onChange={(e) =>
                          setPaymentForm({ ...paymentForm, razorpay_key_secret: e.target.value })
                        }
                      />
                    </Field>
                    <Field
                      label="Razorpay webhook secret"
                      htmlFor="razorpay_webhook_secret"
                      hint={
                        paymentSettings?.webhook_secret_configured
                          ? "Leave blank to keep the current secret."
                          : "Not set yet."
                      }
                    >
                      <PasswordInput
                        id="razorpay_webhook_secret"
                        value={paymentForm.razorpay_webhook_secret}
                        onChange={(e) =>
                          setPaymentForm({
                            ...paymentForm,
                            razorpay_webhook_secret: e.target.value,
                          })
                        }
                      />
                    </Field>
                  </div>
                )}

                {paymentSettingsErrors.length > 0 && (
                  <div className="mb-space-3 border-error bg-error-tint p-space-3 text-error rounded-md border text-[12.5px]">
                    <ul className="pl-space-4 list-disc">
                      {paymentSettingsErrors.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {paymentSettingsSaved && (
                  <p className="mb-space-3 text-success text-[12.5px] font-medium">Saved.</p>
                )}

                <Button type="submit" disabled={savingPaymentSettings}>
                  {savingPaymentSettings ? "Saving…" : "Save payment settings"}
                </Button>
              </form>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

export default function EditTenantPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <EditTenantForm tenantId={Number(id)} />;
}
