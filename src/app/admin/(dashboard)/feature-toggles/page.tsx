"use client";

import { useState } from "react";
import {
  Building2,
  CalendarCheck,
  CalendarClock,
  Clock,
  Copy,
  FileText,
  FlaskConical,
  Globe,
  Headphones,
  HelpCircle,
  History,
  LayoutGrid,
  ListChecks,
  Power,
  PowerOff,
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
import { QuickActionButton } from "@/components/portal/QuickActionButton";
import { QuickActionList } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { cn } from "@/lib/cn";
import { formatShortDateTime } from "@/lib/formatDate";
import { useTenants, type Tenant } from "@/hooks/useTenants";
import { useEditTenant } from "@/hooks/useEditTenant";
import { useTenantAuditLog } from "@/hooks/useTenantAuditLog";
import {
  createFeatureTogglesColumns,
  type FeatureRow,
} from "./_components/feature-toggles-columns";
import { createAppointmentTypeColumns } from "./_components/appointment-type-columns";

// Module/Feature rows (the "Menu & Modules" tab) = the real per-hospital
// hospitals.enabled_features set (flows/patient_identity/menu.py's
// REAL_FEATURES) -- the WhatsApp bot's main-menu rows shown to a PATIENT, a
// deliberately separate concept from admin_capabilities (staff-portal
// screens, managed on the Access Control page instead). Unlike
// admin_capabilities, there's no tenant_type default for these -- they're
// only ever set explicitly, once at onboarding, and changed here after --
// so "Included in Plan"/"Custom Override" genuinely don't apply and are
// shown as "—" rather than fabricated.
//
// The "Appointment Types" tab is a separate real per-hospital allow-list
// (db/repositories/appointment_types.py's `appointment_types` table, not
// enabled_features) -- moved here from Access Control, which only ever
// managed admin_capabilities, a different concept from either tab on this
// page.
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
const OPTIONAL_EXTRAS = ["faq", "consent_privacy", "manage_language", "hospital_info"];

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

  const { entries: auditEntries } = useTenantAuditLog(selectedId);

  const [tab, setTab] = useState<"menu" | "appointment_types">("menu");

  if (!tenant || !form) {
    return <p className="text-ink-400 text-[13px]">Loading…</p>;
  }

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
      <div className="mb-space-4 gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Total Hospitals"
          value={tenants.length}
          deltaPct={null}
          hint="Across all subscriptions"
          icon={Building2}
        />
        <StatTile
          label="Total Features"
          value={allFeatureKeys.length}
          deltaPct={null}
          hint="Configurable WhatsApp menu rows"
          icon={Settings2}
        />
        <StatTile
          label="Custom Overrides"
          value={8}
          deltaPct={null}
          hint="Hospitals with overrides"
          icon={Users}
          mock
        />
        <StatTile
          label="Pending Changes"
          value={pendingChanges}
          deltaPct={null}
          hint={hasUnsaved ? "Unsaved — click Save Changes" : "All changes applied"}
          icon={Clock}
          tint={hasUnsaved ? "clay" : "success"}
        />
      </div>

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
                <p className="text-hint mb-space-3">
                  &quot;Included in Plan&quot; / &quot;Custom Override&quot; don&apos;t apply to
                  WhatsApp features (no plan-based defaults exist for these) — shown as &quot;—&quot;
                  for layout parity.
                </p>

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
                <span className="gap-space-1 flex items-center">
                  <span className="text-ink-900 font-semibold">30 Sep 2026</span>
                  <Badge tone="clay">Mock</Badge>
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-400">Users Allowed</span>
                <span className="gap-space-1 flex items-center">
                  <span className="text-ink-900 font-semibold">120</span>
                  <Badge tone="clay">Mock</Badge>
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
              <div className="flex items-center justify-between">
                <span className="text-ink-400">Support Level</span>
                <span className="gap-space-1 flex items-center">
                  <span className="text-ink-900 font-semibold">Priority</span>
                  <Badge tone="clay">Mock</Badge>
                </span>
              </div>
            </div>
          </Card>

          <Card className="p-space-4">
            <PanelHeader
              title="Quick Actions"
              subtitle="Common feature control actions for the selected hospital."
            />
            <QuickActionList
              size="sm"
              columns={2}
              actions={[
                {
                  label: "Enable All Features",
                  icon: Power,
                  onClick: () => setForm({ ...form, enabled_features: allFeatureKeys }),
                },
                {
                  label: "Disable Optional Extras",
                  icon: PowerOff,
                  onClick: () =>
                    setForm({
                      ...form,
                      enabled_features: form.enabled_features.filter(
                        (k) => !OPTIONAL_EXTRAS.includes(k),
                      ),
                    }),
                },
                {
                  label: "Reset to Saved",
                  icon: RotateCcw,
                  onClick: () => setForm({ ...form, enabled_features: tenant.enabled_features }),
                },
              ]}
            >
              {/* No real "feature profile" concept to clone from yet -- kept
              full-color (not disabled/greyed) with a no-op onClick and a
              "Mock" badge instead. */}
              <div className="relative">
                <QuickActionButton
                  label="Clone Feature Profile"
                  icon={Copy}
                  size="sm"
                  onClick={() => {}}
                />
                <Badge tone="clay" className="absolute -top-2 -right-2">
                  Mock
                </Badge>
              </div>
            </QuickActionList>
          </Card>

          <Card className="p-space-4">
            <PanelHeader title="Recent Feature Changes" />
            {!auditEntries ? (
              <p className="text-ink-400 py-space-3 text-center text-[12.5px]">Loading…</p>
            ) : auditEntries.length === 0 ? (
              <p className="text-ink-400 py-space-3 text-center text-[12.5px]">No changes yet.</p>
            ) : (
              <ul className="divide-line divide-y">
                {auditEntries.slice(0, 5).map((entry) => (
                  <li key={entry.id} className="py-space-2 gap-space-0.5 flex flex-col text-[12px]">
                    <div className="flex items-center justify-between">
                      <span className="gap-space-1 text-ink-900 flex items-center font-semibold">
                        <History size={12} /> {entry.action}
                      </span>
                      <span className="text-ink-400">{formatShortDateTime(entry.created_at)}</span>
                    </div>
                    <span className="text-ink-600">
                      {entry.after_value
                        ? Object.keys(entry.after_value).join(", ")
                        : entry.entity_type || "—"}{" "}
                      · {entry.actor_label}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

export default function FeatureTogglesPage() {
  const { tenants, error } = useTenants();
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const activeId = selectedId ?? tenants?.[0]?.id ?? null;

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
        <FeatureTogglesContent
          tenants={tenants}
          selectedId={activeId as number}
          onSelect={setSelectedId}
        />
      )}
    </div>
  );
}
