import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";
import { validateReminderOffsetsHours } from "@/lib/validation/reminderOffsets";
import { toast } from "@/lib/toast";

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

function formFromTenant(t: TenantDetail): TenantFormState {
  return {
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
  };
}

function tenantQueryKey(tenantId: number) {
  return ["admin-tenant", tenantId] as const;
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
      toast.success(updated.is_allowed ? `${updated.label} allowed` : `${updated.label} disallowed`);
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
    appointmentTypeError,
    toggleFeature,
    resetCapabilitiesToDefaults,
    toggleCapability,
    toggleAppointmentTypeAllowed,
    handleSubmit,
  };
}
