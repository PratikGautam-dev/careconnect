"use client";

import { useState } from "react";
import {
  Building2,
  CalendarCheck,
  CalendarClock,
  Clock,
  FileText,
  FlaskConical,
  Globe,
  Headphones,
  HelpCircle,
  LayoutGrid,
  ListChecks,
  RotateCcw,
  Save,
  Settings2,
  ShieldCheck,
  Stethoscope,
  Users,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { AuditActivityTable } from "@/components/audit/AuditActivityTable";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/formatDate";
import { useTenants, type Tenant } from "@/hooks/useTenants";
import { useAdminSubscriptions } from "@/hooks/useAdminSubscriptions";
import { useEditTenant } from "@/hooks/useEditTenant";
import { useTenantAuditLog } from "@/hooks/useTenantAuditLog";
import {
  createFeatureTogglesColumns,
  type FeatureRow,
} from "./_components/feature-toggles-columns";
import { createAppointmentTypeColumns } from "./_components/appointment-type-columns";

const FEATURE_ICONS: Record<string, LucideIcon> = {
  book_doctor_appointment: CalendarCheck,
  tests_diagnostics: FlaskConical,
  procedure: Stethoscope,
  reschedule: CalendarClock,
  cancel: XCircle,
  view_appointments: ListChecks,
  reports_prescriptions: FileText,
  manage_patients: Users,
  consent_privacy: ShieldCheck,
  manage_language: Globe,
  hospital_info: Building2,
  reception_handoff: Headphones,
  faq: HelpCircle,
};

const TENANT_TYPE_LABELS: Record<string, string> = { hospital: "Hospital", clinic: "Clinic" };

function PanelHeader({
  title,
  subtitle,
  mock,
}: {
  title: string;
  subtitle?: string;
  mock?: boolean;
}) {
  return (
    <div className="mb-space-3 gap-space-3 flex items-start justify-between">
      <div>
        <h3 className="text-label text-ink-900 font-bold">{title}</h3>
        {subtitle && <p className="text-hint mt-space-0.5">{subtitle}</p>}
      </div>
      {mock && <Badge tone="clay">Mock</Badge>}
    </div>
  );
}

function FeatureTogglesContent({
  tenants,
  selectedId,
  onSelect,
}: {
  tenants: Tenant[];
  selectedId: number;
  onSelect: (id: number) => void;
}) {
  const {
    tenant,
    form,
    setForm,
    toggleFeature,
    toggleAppointmentTypeAllowed,
    appointmentTypeError,
    handleSubmit,
    saving,
    saved,
    errors,
  } = useEditTenant(selectedId);

  const { subscriptions } = useAdminSubscriptions();

  const [tab, setTab] = useState<"menu" | "appointment_types">("menu");

  if (!tenant || !form) {
    return <p className="text-ink-400 text-[13px]">Loading…</p>;
  }

  const subscription = subscriptions?.find((s) => s.hospital_id === tenant.id) ?? null;

  const allFeatureKeys = Object.keys(tenant.feature_default_labels);
  // Unsaved local edits: feature keys where the form's checked state
  // differs from what's actually saved (tenant.enabled_features) -- real,
  // computed client-side, not the same thing as a "plan override" (which
  // doesn't apply here, see this file's own top comment).
  const pendingChanges = allFeatureKeys.filter(
    (k) => form.enabled_features.includes(k) !== tenant.enabled_features.includes(k),
  ).length;
  const hasUnsaved = pendingChanges > 0;

  function submit() {
    handleSubmit({ preventDefault() {} } as React.FormEvent);
  }

  return (
    <div>
      <StatTileGrid cols={3} className="mb-space-4">
        <StatTile label="Total Hospitals" value={tenants.length} icon={Building2} />
        <StatTile label="Total Features" value={allFeatureKeys.length} icon={Settings2} />
        <StatTile
          label="Pending Changes"
          value={pendingChanges}
          icon={Clock}
          tint={hasUnsaved ? "clay" : "success"}
        />
      </StatTileGrid>

      <Card className="p-space-4 mb-space-4">
        <div className="gap-space-4 flex flex-wrap items-end justify-between">
          <div className="gap-space-4 flex flex-wrap items-end">
            <div>
              <label className="text-hint mb-space-1 block">Select Hospital</label>
              <select
                value={selectedId}
                onChange={(e) => onSelect(Number(e.target.value))}
                className="border-line bg-card px-space-3 text-ink-900 h-10 min-w-60 rounded-md border text-[13px]"
              >
                {tenants.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-hint mb-space-1 block">Plan (tenant type)</label>
              <select
                value={form.tenant_type}
                disabled
                className="border-line bg-paper px-space-3 text-ink-600 h-10 min-w-45 rounded-md border text-[13px]"
              >
                <option value={form.tenant_type}>
                  {TENANT_TYPE_LABELS[form.tenant_type] || form.tenant_type}
                </option>
              </select>
            </div>
            <div>
              <p className="text-hint mb-space-1">Feature Configuration Status</p>
              <Badge tone={hasUnsaved ? "clay" : "success"}>
                {hasUnsaved ? "Unsaved Changes" : "Custom Configuration"}
              </Badge>
            </div>
          </div>
          <button
            type="button"
            onClick={submit}
            disabled={saving}
            className="bg-brand-600 hover:bg-brand-700 gap-space-2 px-space-4 flex h-10 shrink-0 items-center rounded-md text-[13px] font-semibold text-white transition-colors duration-150 disabled:opacity-60"
          >
            <Save size={15} /> {saving ? "Saving…" : "Save Changes"}
          </button>
        </div>
        {saved && <p className="text-success mt-space-2 text-[12.5px]">Saved.</p>}
        {errors.length > 0 && <p className="text-error mt-space-2 text-[12.5px]">{errors[0]}</p>}
      </Card>

      <div className="mb-space-4 gap-space-1 border-line bg-card inline-flex rounded-md border p-1">
        <button
          type="button"
          onClick={() => setTab("menu")}
          className={cn(
            "px-space-3 gap-space-2 flex items-center rounded-sm py-1.5 text-[12.5px] font-semibold transition-colors duration-150",
            tab === "menu" ? "bg-brand-600 text-white" : "text-ink-600 hover:bg-paper",
          )}
        >
          <LayoutGrid size={14} /> WhatsApp Features
        </button>
        <button
          type="button"
          onClick={() => setTab("appointment_types")}
          className={cn(
            "px-space-3 gap-space-2 flex items-center rounded-sm py-1.5 text-[12.5px] font-semibold transition-colors duration-150",
            tab === "appointment_types" ? "bg-brand-600 text-white" : "text-ink-600 hover:bg-paper",
          )}
        >
          <ListChecks size={14} /> Appointment Types
        </button>
      </div>

      <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card className="p-space-4">
            {tab === "menu" ? (
              <>
                <div className="mb-space-1 gap-space-3 flex flex-wrap items-start justify-between">
                  <div>
                    <h3 className="text-label text-ink-900 font-bold">WhatsApp Menu Features</h3>
                    <p className="text-hint mt-space-1">
                      Enable or disable WhatsApp menu features for the selected hospital.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, enabled_features: tenant.enabled_features })}
                    className="text-brand-600 gap-space-1 flex items-center text-[12.5px] font-semibold hover:underline"
                  >
                    <RotateCcw size={13} /> Discard Unsaved Changes
                  </button>
                </div>

                <DataTable<FeatureRow>
                  columns={createFeatureTogglesColumns({ onToggle: toggleFeature })}
                  data={allFeatureKeys.map((key) => ({
                    key,
                    label: tenant.feature_default_labels[key] || key,
                    icon: FEATURE_ICONS[key] || Settings2,
                    enabled: form.enabled_features.includes(key),
                  }))}
                  getRowId={(row) => row.key}
                  pageSize={25}
                />
              </>
            ) : (
              <>
                <div className="mb-space-3">
                  <h3 className="text-label text-ink-900 font-bold">Appointment Types</h3>
                  <p className="text-hint mt-space-1">
                    Which types this hospital may offer at all. Unchecking one also turns it off in
                    the hospital&apos;s own portal immediately — the hospital can then only switch
                    it back on if you re-allow it here first.
                  </p>
                </div>
                {appointmentTypeError && (
                  <p className="mb-space-2 text-error text-[12.5px]">{appointmentTypeError}</p>
                )}

                <DataTable
                  columns={createAppointmentTypeColumns({ onToggle: toggleAppointmentTypeAllowed })}
                  data={tenant.appointment_types}
                  getRowId={(row) => row.id}
                  pageSize={25}
                />
              </>
            )}
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <PanelHeader title="Hospital &amp; Plan Summary" />
            <div className="space-y-space-2 text-[12.5px]">
              <div className="flex items-center justify-between">
                <span className="text-ink-400">Hospital</span>
                <span className="text-ink-900 font-semibold">{tenant.name}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-400">Plan</span>
                <span className="text-ink-900 font-semibold">
                  {TENANT_TYPE_LABELS[form.tenant_type] || form.tenant_type}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-400">Renewal Date</span>
                <span className="text-ink-900 font-semibold">
                  {subscription ? formatDate(subscription.renewal_date) : "—"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-400">Users Allowed</span>
                <span className="text-ink-900 font-semibold">
                  {subscription
                    ? `${subscription.seats_used} / ${subscription.max_users ?? "Unlimited"}`
                    : "—"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-400">Features Active</span>
                <span className="text-ink-900 font-semibold">
                  {form.enabled_features.length} / {allFeatureKeys.length}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-400">Configuration Status</span>
                <Badge tone={hasUnsaved ? "clay" : "success"}>
                  {hasUnsaved ? "Unsaved" : "Applied"}
                </Badge>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ===== Audit Activity Table (moved outside grid for full width) =====
function FeatureAuditActivityTable({
  auditEntries,
  tenant,
}: {
  auditEntries: import("@/hooks/useTenantAuditLog").TenantAuditEntry[];
  tenant: import("@/hooks/useTenants").Tenant | null;
}) {
  const entries = (auditEntries ?? []).map((e) => ({
    ...e,
    hospital_name: tenant?.name ?? null,
    hospital_id: tenant?.id ?? null,
  }));
  return (
    <AuditActivityTable
      entries={entries}
      isLoading={!auditEntries}
      title="Recent Feature Changes"
      subtitle="Recent changes to feature toggles for the selected hospital."
      emptyMessage="No feature changes yet."
      showActorLevelFilter={false}
      showHospitalColumn={false}
    />
  );
}

export default function FeatureTogglesPage() {
  const { tenants, error } = useTenants();
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const activeId = selectedId ?? tenants?.[0]?.id ?? null;
  const { entries: auditEntries } = useTenantAuditLog(activeId);
  // auditEntries is passed to FeatureAuditActivityTable below

  return (
    <div>
      <div className="mb-space-5">
        <h1 className="text-display">Feature Toggles</h1>
        <p className="text-ink-600 text-[13px]">
          Control which WhatsApp bot menu features each hospital can access and use.
        </p>
      </div>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      {!tenants ? (
        <p className="text-ink-400 text-[13px]">Loading…</p>
      ) : tenants.length === 0 ? (
        <p className="text-ink-400 text-[13px]">No hospitals onboarded yet.</p>
      ) : (
        <>
          <FeatureTogglesContent
            tenants={tenants}
            selectedId={activeId as number}
            onSelect={setSelectedId}
          />
          <FeatureAuditActivityTable
            auditEntries={auditEntries ?? []}
            tenant={tenants?.find((t) => t.id === activeId) ?? null}
          />
        </>
      )}
    </div>
  );
}
