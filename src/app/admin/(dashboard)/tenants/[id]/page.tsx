"use client";

import { use } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { Switch } from "@/components/ui/Switch";
import { useEditTenant } from "@/hooks/useEditTenant";
import { useAdminSubscriptions } from "@/hooks/useAdminSubscriptions";
import { useAdminBillingRecords } from "@/hooks/useAdminBillingRecords";
import { createTenantSubscriptionColumns } from "./_components/tenant-subscription-columns";
import { createBillingColumns } from "../../plans-billing/_components/billing-columns";

function EditTenantForm({ tenantId }: { tenantId: number }) {
  const {
    tenant,
    form,
    setForm,
    error,
    errors,
    saving,
    saved,
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

  const { subscriptions } = useAdminSubscriptions();
  const { records: billingRecords } = useAdminBillingRecords();

  // Both real lists are global (every hospital), scoped down to just this
  // tenant here -- list_subscriptions() always has exactly one row per
  // hospital (status "unassigned" until a plan is set), so this is
  // currently a single-row table, but built as a real DataTable rather than
  // a one-off summary so it holds up if subscription HISTORY (more than one
  // row per hospital) is ever added later.
  const subscriptionsForTenant = (subscriptions ?? []).filter((s) => s.hospital_id === tenantId);
  const billingForTenant = (billingRecords ?? []).filter((r) => r.hospital_id === tenantId);

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

              <p className="text-hint mb-space-4">
                Staff-portal module access moved to{" "}
                <Link href="/admin/access-control" className="text-brand-600 hover:underline">
                  Access Control
                </Link>
                . WhatsApp menu features and appointment types moved to{" "}
                <Link href="/admin/feature-toggles" className="text-brand-600 hover:underline">
                  Feature Toggles
                </Link>
                . Appointment reminder offsets and template name, and the WhatsApp welcome message,
                are managed by the hospital itself, under its own Settings → Notifications /
                General tabs.
              </p>

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

          <Card className="p-space-5 mt-space-4">
            <div className="mb-space-2 gap-space-3 flex flex-wrap items-start justify-between">
              <div>
                <p className="text-eyebrow mb-space-1">Subscription</p>
                <h2 className="text-display text-[18px]">Plan &amp; renewal</h2>
              </div>
              <Link
                href="/admin/subscriptions"
                className="text-brand-600 text-[13px] font-semibold hover:underline"
              >
                Manage subscriptions →
              </Link>
            </div>
            <p className="text-body mb-space-4">
              Assigning a plan, starting a trial or cancelling billing all happen on Subscriptions —
              this is a read-only summary for this hospital.
            </p>
            <DataTable
              columns={createTenantSubscriptionColumns()}
              data={subscriptionsForTenant}
              getRowId={(row) => String(row.hospital_id)}
              loading={!subscriptions}
              emptyMessage="No subscription for this hospital yet."
            />
          </Card>

          <Card className="p-space-5 mt-space-4">
            <p className="text-eyebrow mb-space-1">Billing</p>
            <h2 className="text-display mb-space-4 text-[18px]">Billing history</h2>
            <DataTable
              columns={createBillingColumns()}
              data={billingForTenant}
              getRowId={(row) => String(row.id)}
              loading={!billingRecords}
              emptyMessage="No billing records yet -- these appear once this hospital's real Razorpay billing starts collecting payments."
              pageSize={10}
            />
          </Card>
        </>
      )}
    </div>
  );
}

export default function EditTenantPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <EditTenantForm tenantId={Number(id)} />;
}
