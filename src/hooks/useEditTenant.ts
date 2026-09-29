import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";
import { validateReminderOffsetsHours } from "@/lib/validation/reminderOffsets";
import { toast } from "@/lib/toast";

// Flat, primitives-only form objects (payment/fee settings below) -- enough
// to tell "nothing to save" from a real edit without a deep-equal library.
function shallowEqual<T extends Record<string, unknown>>(a: T, b: T): boolean {
  return Object.keys(a).every((k) => a[k] === b[k]);
}

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
  is_active: boolean;
  // Which Google account(s) own this hospital's portal -- empty for a
  // hospital onboarded before Google sign-in existed (admin/tenants_api.py's
  // _tenant_detail(), db.get_owners_for_hospital()).
  owners: { id: number; email: string; name: string | null }[];
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
  data_tier: string;
  api_base_url: string;
  api_key: string;
  enabled_features: string[];
  tenant_type: string;
  admin_capabilities: string[];
};

function formFromTenant(t: TenantDetail): TenantFormState {
  return {
    name: t.name,
    whatsapp_phone_number_id: t.whatsapp_phone_number_id,
    access_token: "",
    app_secret: "",
    welcome_message_text: t.welcome_message_text,
    reminder_offsets_hours: t.reminder_offsets_hours,
    reminder_template_name: t.reminder_template_name,
    data_tier: t.data_tier,
    api_base_url: t.external_api_base_url,
    api_key: t.external_api_key,
    enabled_features: t.enabled_features,
    tenant_type: t.tenant_type,
    admin_capabilities: t.admin_capabilities,
  };
}

export function tenantQueryKey(tenantId: number) {
  return ["admin-tenant", tenantId] as const;
}

// Same "is there actually anything to save" question shallowEqual answers
// for the fee/payment forms below, but TenantFormState carries two
// multi-select array fields (enabled_features/admin_capabilities) that
// reference-compare unequal even with identical contents (a fresh array is
// built on every toggle) -- order-independent membership compare for those
// two, plain equality for everything else.
function sameMembers(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const sortedA = [...a].sort();
  const sortedB = [...b].sort();
  return sortedA.every((v, i) => v === sortedB[i]);
}

function tenantFormEqual(a: TenantFormState, b: TenantFormState): boolean {
  return (
    a.name === b.name &&
    a.whatsapp_phone_number_id === b.whatsapp_phone_number_id &&
    a.access_token === b.access_token &&
    a.app_secret === b.app_secret &&
    a.welcome_message_text === b.welcome_message_text &&
    a.reminder_offsets_hours === b.reminder_offsets_hours &&
    a.reminder_template_name === b.reminder_template_name &&
    a.data_tier === b.data_tier &&
    a.api_base_url === b.api_base_url &&
    a.api_key === b.api_key &&
    a.tenant_type === b.tenant_type &&
    sameMembers(a.enabled_features, b.enabled_features) &&
    sameMembers(a.admin_capabilities, b.admin_capabilities)
  );
}

export type PaymentSettingsDetail = {
  payment_mode: "platform" | "hospital_own";
  razorpay_key_id: string | null;
  key_secret_configured: boolean;
  webhook_secret_configured: boolean;
  // This hospital's own GST/platform-fee override -- only applied when
  // override_fees is true; otherwise the default_* fields below (the
  // platform-wide rate) are what's actually charged.
  override_fees: boolean;
  gst_enabled: boolean;
  gst_percent: number | null;
  platform_fee_enabled: boolean;
  platform_fee_percent: number | null;
  default_gst_enabled: boolean;
  default_gst_percent: number | null;
  default_platform_fee_enabled: boolean;
  default_platform_fee_percent: number | null;
};

export type FeeSettingsFormState = {
  override_fees: boolean;
  gst_enabled: boolean;
  gst_percent: string;
  platform_fee_enabled: boolean;
  platform_fee_percent: string;
};

function feeFormFromSettings(s: PaymentSettingsDetail): FeeSettingsFormState {
  return {
    override_fees: s.override_fees,
    gst_enabled: s.gst_enabled,
    gst_percent: s.gst_percent === null ? "" : String(s.gst_percent),
    platform_fee_enabled: s.platform_fee_enabled,
    platform_fee_percent: s.platform_fee_percent === null ? "" : String(s.platform_fee_percent),
  };
}

export type PaymentSettingsFormState = {
  payment_mode: "platform" | "hospital_own";
  razorpay_key_id: string;
  razorpay_key_secret: string; // blank = keep current
  razorpay_webhook_secret: string; // blank = keep current
};

function paymentFormFromSettings(s: PaymentSettingsDetail): PaymentSettingsFormState {
  return {
    payment_mode: s.payment_mode,
    razorpay_key_id: s.razorpay_key_id ?? "",
    razorpay_key_secret: "",
    razorpay_webhook_secret: "",
  };
}

export function paymentSettingsQueryKey(tenantId: number) {
  return ["admin-tenant-payment-settings", tenantId] as const;
}

/** Loads + saves one tenant for the /admin/tenants/[id] edit form, and owns
 * the appointment-type allow-list toggle (its own independent save, not
 * part of the main form submit). Single page, single consumer -- kept as
 * one hook (unlike the Doctors/Staff split) rather than separated into
 * per-mutation hooks nothing else would ever import. */
export function useEditTenant(tenantId: number) {
  const queryClient = useQueryClient();

  const {
    data: tenant,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey: tenantQueryKey(tenantId),
    retry: false,
    queryFn: async () => {
      const result = await adminFetch(`/api/admin/tenants/${tenantId}`);
      return unwrapAdminResult<{ tenant: TenantDetail }>(result).tenant;
    },
  });

  const [seededTenantId, setSeededTenantId] = useState<number | null>(null);
  const [form, setForm] = useState<TenantFormState | null>(null);
  if (tenant && tenant.id !== seededTenantId) {
    setSeededTenantId(tenant.id);
    setForm(formFromTenant(tenant));
  }

  const [errors, setErrors] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const [appointmentTypeError, setAppointmentTypeError] = useState<string | null>(null);

  // Unlike paymentFormDirty/feeFormDirty below, this isn't (yet) used to
  // guard handleSubmit itself -- only to warn a caller (the Access Control
  // page's "Select Hospital" switcher) before it discards in-progress,
  // unsaved capability/feature toggles by re-seeding `form` from a
  // different tenant.
  const formDirty = !!(form && tenant && !tenantFormEqual(form, formFromTenant(tenant)));

  // Payment gateway routing (super-admin only, admin/payment_settings_api.py)
  // -- a genuinely separate resource/endpoint from the tenant fields above,
  // saved independently (same "own mutation, not part of the main form
  // submit" shape as the appointment-type allow-list toggles further down),
  // since it's financial-credential data with its own audit trail.
  const {
    data: paymentSettings,
    error: paymentSettingsQueryError,
    refetch: refetchPaymentSettings,
  } = useQuery({
    queryKey: paymentSettingsQueryKey(tenantId),
    retry: false,
    queryFn: async () => {
      const result = await adminFetch(`/api/admin/tenants/${tenantId}/payment-settings`);
      return unwrapAdminResult<PaymentSettingsDetail>(result);
    },
  });

  const [seededPaymentSettingsTenantId, setSeededPaymentSettingsTenantId] = useState<number | null>(
    null,
  );
  const [paymentForm, setPaymentForm] = useState<PaymentSettingsFormState | null>(null);
  if (paymentSettings && tenantId !== seededPaymentSettingsTenantId) {
    setSeededPaymentSettingsTenantId(tenantId);
    setPaymentForm(paymentFormFromSettings(paymentSettings));
  }
  // Nothing to send if the form still matches what's actually saved --
  // guards the Save button so toggling something back to its original value
  // (or never touching the form at all) can't fire a no-op PATCH.
  const paymentFormDirty = !!(
    paymentForm &&
    paymentSettings &&
    !shallowEqual(paymentForm, paymentFormFromSettings(paymentSettings))
  );

  const [paymentSettingsErrors, setPaymentSettingsErrors] = useState<string[]>([]);
  const [paymentSettingsSaved, setPaymentSettingsSaved] = useState(false);

  // This hospital's own GST/platform-fee override -- same query as payment
  // settings above (one GET already returns both), its own independent
  // save (own PATCH endpoint, own form state) since it's a logically
  // separate section on the page.
  const [seededFeeSettingsTenantId, setSeededFeeSettingsTenantId] = useState<number | null>(null);
  const [feeForm, setFeeForm] = useState<FeeSettingsFormState | null>(null);
  if (paymentSettings && tenantId !== seededFeeSettingsTenantId) {
    setSeededFeeSettingsTenantId(tenantId);
    setFeeForm(feeFormFromSettings(paymentSettings));
  }
  // Same "nothing to save" guard as paymentFormDirty above -- most relevant
  // here since toggling "Use this tenant's own rate" off is itself a no-op
  // for a tenant that already inherits the platform default.
  const feeFormDirty = !!(
    feeForm &&
    paymentSettings &&
    !shallowEqual(feeForm, feeFormFromSettings(paymentSettings))
  );

  const [feeSettingsErrors, setFeeSettingsErrors] = useState<string[]>([]);
  const [feeSettingsSaved, setFeeSettingsSaved] = useState(false);

  const saveFeeSettingsMutation = useMutation({
    mutationFn: async (payload: {
      override_fees: boolean;
      gst_enabled: boolean;
      gst_percent: number | null;
      platform_fee_enabled: boolean;
      platform_fee_percent: number | null;
    }) => {
      const result = await adminFetch(`/api/admin/tenants/${tenantId}/fee-settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapAdminResult<{ status?: string; errors?: string[] }>(result);
    },
  });

  async function handleFeeSettingsSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!feeForm || !feeFormDirty) return;
    setFeeSettingsSaved(false);
    setFeeSettingsErrors([]);
    const gstPercent = feeForm.gst_percent.trim() === "" ? null : Number(feeForm.gst_percent);
    const platformFeePercent =
      feeForm.platform_fee_percent.trim() === "" ? null : Number(feeForm.platform_fee_percent);
    if (gstPercent !== null && !Number.isFinite(gstPercent)) {
      setFeeSettingsErrors(["GST % must be a number."]);
      return;
    }
    if (platformFeePercent !== null && !Number.isFinite(platformFeePercent)) {
      setFeeSettingsErrors(["Platform fee % must be a number."]);
      return;
    }
    try {
      const data = await saveFeeSettingsMutation.mutateAsync({
        override_fees: feeForm.override_fees,
        gst_enabled: feeForm.gst_enabled,
        gst_percent: gstPercent,
        platform_fee_enabled: feeForm.platform_fee_enabled,
        platform_fee_percent: platformFeePercent,
      });
      if (data.errors?.length) {
        setFeeSettingsErrors(data.errors);
        toast.error("Couldn't save fee settings", data.errors[0]);
        return;
      }
      toast.success("Fee settings saved");
      setFeeSettingsSaved(true);
      setSeededPaymentSettingsTenantId(null);
      setSeededFeeSettingsTenantId(null);
      refetchPaymentSettings();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setFeeSettingsErrors([message]);
      toast.error("Couldn't save fee settings", message);
    }
  }

  const savePaymentSettingsMutation = useMutation({
    mutationFn: async (payload: PaymentSettingsFormState) => {
      const result = await adminFetch(`/api/admin/tenants/${tenantId}/payment-settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapAdminResult<{ status?: string; errors?: string[] }>(result);
    },
  });

  async function handlePaymentSettingsSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!paymentForm || !paymentFormDirty) return;
    setPaymentSettingsSaved(false);
    setPaymentSettingsErrors([]);
    try {
      const data = await savePaymentSettingsMutation.mutateAsync(paymentForm);
      if (data.errors?.length) {
        setPaymentSettingsErrors(data.errors);
        toast.error("Couldn't save payment settings", data.errors[0]);
        return;
      }
      toast.success("Payment settings saved");
      setPaymentSettingsSaved(true);
      // Secrets are never echoed back -- refetch so the "configured" flags
      // and the blanked-out secret fields reflect what was just saved.
      setSeededPaymentSettingsTenantId(null);
      refetchPaymentSettings();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setPaymentSettingsErrors([message]);
      toast.error("Couldn't save payment settings", message);
    }
  }

  const saveMutation = useMutation({
    mutationFn: async (payload: TenantFormState) => {
      const result = await adminFetch(`/api/admin/tenants/${tenantId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapAdminResult<{ tenant?: TenantDetail; errors?: string[] }>(result);
    },
  });

  // Hospital account Active/Inactive kill switch (admin/tenants_api.py's
  // own status endpoint, separate from the main tenant PATCH) -- applies
  // immediately on confirm, no separate "Save" step, since the page's own
  // ConfirmDialog IS the confirmation step.
  const updateStatusMutation = useMutation({
    mutationFn: async (isActive: boolean) => {
      const result = await adminFetch(`/api/admin/tenants/${tenantId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: isActive }),
      });
      return unwrapAdminResult<{ tenant: TenantDetail }>(result).tenant;
    },
  });

  async function updateTenantStatus(isActive: boolean) {
    try {
      const updated = await updateStatusMutation.mutateAsync(isActive);
      queryClient.setQueryData(tenantQueryKey(tenantId), updated);
      toast.success(isActive ? "Tenant activated" : "Tenant deactivated");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      toast.error("Couldn't update tenant status", message);
      throw err;
    }
  }

  const toggleAppointmentTypeMutation = useMutation({
    mutationFn: async ({
      appointmentTypeId,
      isAllowed,
    }: {
      appointmentTypeId: string;
      isAllowed: boolean;
    }) => {
      const result = await adminFetch(
        `/api/admin/tenants/${tenantId}/appointment-types/${appointmentTypeId}/allowed`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_allowed: isAllowed }),
        },
      );
      return unwrapAdminResult<{ appointment_type: AppointmentTypeRow }>(result).appointment_type;
    },
  });

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

  async function toggleAppointmentTypeAllowed(appointmentTypeId: string, isAllowed: boolean) {
    setAppointmentTypeError(null);
    try {
      const updated = await toggleAppointmentTypeMutation.mutateAsync({
        appointmentTypeId,
        isAllowed,
      });
      toast.success(
        updated.is_allowed ? `${updated.label} allowed` : `${updated.label} disallowed`,
      );
      queryClient.setQueryData(tenantQueryKey(tenantId), (prev: TenantDetail | undefined) =>
        prev
          ? {
              ...prev,
              appointment_types: prev.appointment_types.map((t) =>
                t.id === updated.id ? updated : t,
              ),
            }
          : prev,
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setAppointmentTypeError(message);
      toast.error("Couldn't update appointment type", message);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    // Same client-side check Settings -> Notifications' own reminder-
    // offsets field uses (src/lib/validation/reminderOffsets.ts) -- the
    // backend's own parser silently drops anything it can't read rather
    // than rejecting the request, so catch a typo here instead of letting
    // it silently change what actually gets saved.
    const offsetsInvalid = validateReminderOffsetsHours(form.reminder_offsets_hours);
    if (offsetsInvalid) {
      setErrors([offsetsInvalid]);
      return;
    }
    setSaved(false);
    setErrors([]);
    try {
      const data = await saveMutation.mutateAsync(form);
      if (data.errors?.length) {
        setErrors(data.errors);
        toast.error("Couldn't save tenant", data.errors[0]);
        return;
      }
      toast.success("Tenant saved");
      setSaved(true);
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setErrors([message]);
      toast.error("Couldn't save tenant", message);
    }
  }

  return {
    tenant: tenant ?? null,
    form,
    setForm,
    error: queryError ? (queryError as Error).message : null,
    errors,
    saving: saveMutation.isPending,
    saved,
    formDirty,
    appointmentTypeError,
    toggleFeature,
    resetCapabilitiesToDefaults,
    toggleCapability,
    toggleAppointmentTypeAllowed,
    handleSubmit,
    updateTenantStatus,
    updatingTenantStatus: updateStatusMutation.isPending,
    paymentSettings: paymentSettings ?? null,
    paymentForm,
    setPaymentForm,
    paymentSettingsError: paymentSettingsQueryError
      ? (paymentSettingsQueryError as Error).message
      : null,
    paymentSettingsErrors,
    savingPaymentSettings: savePaymentSettingsMutation.isPending,
    paymentSettingsSaved,
    paymentFormDirty,
    handlePaymentSettingsSubmit,
    feeForm,
    setFeeForm,
    feeSettingsErrors,
    savingFeeSettings: saveFeeSettingsMutation.isPending,
    feeSettingsSaved,
    feeFormDirty,
    handleFeeSettingsSubmit,
  };
}
