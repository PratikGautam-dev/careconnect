"use client";

import { use, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
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
    paymentFormDirty,
    handlePaymentSettingsSubmit,
    feeForm,
    setFeeForm,
    feeSettingsErrors,
    savingFeeSettings,
    feeSettingsSaved,
    feeFormDirty,
    handleFeeSettingsSubmit,
    updateTenantStatus,
    updatingTenantStatus,
  } = useEditTenant(tenantId);

  const { subscriptions } = useAdminSubscriptions();
  const { records: billingRecords } = useAdminBillingRecords();

  // Confirmation step for the Active/Inactive kill switch below -- holds
  // the value the operator is about to switch TO, null when no confirm
  // dialog is open.
  const [pendingStatus, setPendingStatus] = useState<boolean | null>(null);

  async function confirmStatusChange() {
    if (pendingStatus === null) return;
    try {
      await updateTenantStatus(pendingStatus);
      setPendingStatus(null);
    } catch {
      // updateTenantStatus already toasts the error -- leave the dialog
      // open so the operator can retry instead of silently losing the intent.
    }
  }

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
            <div className="mb-space-4 gap-space-3 flex flex-wrap items-start justify-between">
              <div>
                <p className="text-eyebrow mb-space-1">Editing tenant #{tenant.id}</p>
                <h1 className="text-display">{tenant.name}</h1>
              </div>
              <div className="gap-space-3 flex items-center">
                <Badge tone={tenant.is_active ? "success" : "neutral"}>
                  {tenant.is_active ? "Active" : "Inactive"}
                </Badge>
                <Switch
                  checked={tenant.is_active}
                  onChange={() => setPendingStatus(!tenant.is_active)}
                  disabled={updatingTenantStatus}
                  aria-label="Tenant account active"
                />
              </div>
            </div>
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
                are managed by the hospital itself, under its own Settings → Notifications / General
                tabs.
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

                <Button type="submit" disabled={savingPaymentSettings || !paymentFormDirty}>
                  {savingPaymentSettings ? "Saving…" : "Save payment settings"}
                </Button>
              </form>
            </Card>
          )}

          {feeForm && (
            <Card className="p-space-5 mt-space-4">
              <p className="text-eyebrow mb-space-1">Payment gateway</p>
              <h2 className="text-display mb-space-2 text-[18px]">GST &amp; platform fee</h2>
              <p className="text-body mb-space-4">
                By default this hospital is charged the platform-wide rate, set in Platform Settings
                → General. A hospital running its own Razorpay account can pick its own rate here
                instead.
              </p>

              <form onSubmit={handleFeeSettingsSubmit}>
                <div className="mb-space-4 gap-space-3 flex items-center">
                  <Switch
                    checked={feeForm.override_fees}
                    onChange={() =>
                      setFeeForm({ ...feeForm, override_fees: !feeForm.override_fees })
                    }
                    aria-label="Use this tenant's own GST/platform fee rate"
                  />
                  <span className="text-[14px] font-medium">
                    {feeForm.override_fees
                      ? "Using this tenant's own rate"
                      : "Using the platform's rate (default)"}
                  </span>
                </div>

                {feeForm.override_fees ? (
                  <div className="gap-x-space-4 gap-y-space-3 grid grid-cols-1 md:grid-cols-2">
                    <div>
                      <div className="mb-space-2 gap-space-2 flex items-center">
                        <Switch
                          checked={feeForm.gst_enabled}
                          onChange={() =>
                            setFeeForm({ ...feeForm, gst_enabled: !feeForm.gst_enabled })
                          }
                          aria-label="Charge GST for this tenant"
                        />
                        <span className="text-[13px] font-medium">Charge GST</span>
                      </div>
                      <Field label="GST (%)" htmlFor="tenant_gst_percent">
                        <Input
                          id="tenant_gst_percent"
                          type="number"
                          min={0}
                          max={50}
                          step="0.01"
                          placeholder="0"
                          disabled={!feeForm.gst_enabled}
                          value={feeForm.gst_percent}
                          onChange={(e) => setFeeForm({ ...feeForm, gst_percent: e.target.value })}
                        />
                      </Field>
                    </div>
                    <div>
                      <div className="mb-space-2 gap-space-2 flex items-center">
                        <Switch
                          checked={feeForm.platform_fee_enabled}
                          onChange={() =>
                            setFeeForm({
                              ...feeForm,
                              platform_fee_enabled: !feeForm.platform_fee_enabled,
                            })
                          }
                          aria-label="Charge platform fee for this tenant"
                        />
                        <span className="text-[13px] font-medium">Charge platform fee</span>
                      </div>
                      <Field label="Platform fee (%)" htmlFor="tenant_platform_fee_percent">
                        <Input
                          id="tenant_platform_fee_percent"
                          type="number"
                          min={0}
                          max={50}
                          step="0.01"
                          placeholder="0"
                          disabled={!feeForm.platform_fee_enabled}
                          value={feeForm.platform_fee_percent}
                          onChange={(e) =>
                            setFeeForm({ ...feeForm, platform_fee_percent: e.target.value })
                          }
                        />
                      </Field>
                    </div>
                  </div>
                ) : (
                  <p className="mb-space-4 bg-canvas p-space-3 text-ink-600 rounded-md text-[13px]">
                    Currently inherits the platform default:{" "}
                    <span className="font-bold">
                      GST{" "}
                      {paymentSettings?.default_gst_enabled
                        ? `${paymentSettings.default_gst_percent ?? 0}%`
                        : "off"}
                    </span>
                    {", "}
                    <span className="font-bold">
                      platform fee{" "}
                      {paymentSettings?.default_platform_fee_enabled
                        ? `${paymentSettings.default_platform_fee_percent ?? 0}%`
                        : "off"}
                    </span>
                    .
                  </p>
                )}

                {feeSettingsErrors.length > 0 && (
                  <div className="mb-space-3 border-error bg-error-tint p-space-3 text-error rounded-md border text-[12.5px]">
                    <ul className="pl-space-4 list-disc">
                      {feeSettingsErrors.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {feeSettingsSaved && (
                  <p className="mb-space-3 text-success text-[12.5px] font-medium">Saved.</p>
                )}

                <Button type="submit" disabled={savingFeeSettings || !feeFormDirty}>
                  {savingFeeSettings ? "Saving…" : "Save fee settings"}
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

          <ConfirmDialog
            open={pendingStatus !== null}
            title={pendingStatus ? "Activate tenant" : "Deactivate tenant"}
            message={
              pendingStatus
                ? `Activating will allow ${tenant.name} to use all the plan features associated with the hospital again, including taking bookings through WhatsApp.`
                : `Switching off will restrict all of the services of ${tenant.name}. No booking can be made here anymore -- its WhatsApp will reply that the ${tenant.tenant_type === "clinic" ? "clinic's" : "hospital's"} service is currently inactive.`
            }
            confirmLabel={pendingStatus ? "Activate" : "Deactivate"}
            destructive={!pendingStatus}
            busy={updatingTenantStatus}
            onConfirm={confirmStatusChange}
            onCancel={() => setPendingStatus(null)}
          />
        </>
      )}
    </div>
  );
}

export default function EditTenantPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <EditTenantForm tenantId={Number(id)} />;
}
