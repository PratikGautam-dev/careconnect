"use client";

import { useState } from "react";
import {
  Building2,
  ClipboardCheck,
  Clock,
  Copy,
  FileText,
  History,
  Power,
  RotateCcw,
  Save,
  Settings,
  Shield,
  UserX,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { QuickActionButton } from "@/components/portal/QuickActionButton";
import { QuickActionList } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { cn } from "@/lib/cn";
import { formatDate, formatShortDateTime } from "@/lib/formatDate";
import { CAPABILITY_META } from "@/lib/hospitalCapabilities";
import { useTenants, type Tenant } from "@/hooks/useTenants";
import { useEditTenant } from "@/hooks/useEditTenant";
import { useTenantAuditLog } from "@/hooks/useTenantAuditLog";
import { useAdminSubscriptions } from "@/hooks/useAdminSubscriptions";
import { useAdminPlans } from "@/hooks/useAdminPlans";
import {
  createAccessControlColumns,
  type CapabilityRow,
} from "./_components/access-control-columns";

// Module/Feature rows = the real per-hospital admin_capabilities set
// (portal/capabilities.py, ALL_CAPABILITIES) -- "which staff-portal
// MANAGEMENT screens this tenant can use", a deliberately separate concept
// from hospitals.enabled_features (the WhatsApp bot menu, managed on the
// Feature Toggles page instead). See useEditTenant.ts's TenantDetail type
// for where every field on this page comes from. Labels/icons come from
// src/lib/hospitalCapabilities.ts -- the SAME catalog the staff portal's
// own sidebar reads (PortalSidebar's hasCapability) -- so a capability
// toggled off here disappears from that hospital's nav, not just this
// table, and relabeling a capability only needs to happen in one place.

const TENANT_TYPE_LABELS: Record<string, string> = { hospital: "Hospital", clinic: "Clinic" };

function capabilitiesMatch(a: string[], b: string[]): boolean {
  const sortedA = [...a].sort();
  const sortedB = [...b].sort();
  return sortedA.length === sortedB.length && sortedA.every((v, i) => v === sortedB[i]);
}

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

function AccessControlContent({
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
    toggleCapability,
    resetCapabilitiesToDefaults,
    handleSubmit,
    saving,
    saved,
    errors,
  } = useEditTenant(selectedId);

  const { entries: auditEntries } = useTenantAuditLog(selectedId);
  const { subscriptions } = useAdminSubscriptions();
  const { plans } = useAdminPlans();

  const customCount = tenants.filter((t) => t.has_custom_capabilities).length;

  if (!tenant || !form) {
    return <p className="text-ink-400 text-[13px]">Loading…</p>;
  }

  const includedInPlan = tenant.default_capabilities_by_type[form.tenant_type] ?? [];
  const isCustom = !capabilitiesMatch(form.admin_capabilities, includedInPlan);

  // Real subscription stats (useAdminSubscriptions / db.list_subscriptions())
  // -- same source the Super Admin Dashboard and /admin/subscriptions use.
  const now = new Date();
  const activeSubscriptionsCount =
    subscriptions?.filter((s) => s.status === "active").length ?? null;
  const expiringThisMonthCount =
    subscriptions?.filter((s) => {
      if (!s.renewal_date) return false;
      const d = new Date(`${s.renewal_date}T00:00:00`);
      return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
    }).length ?? null;
  const subscription = subscriptions?.find((s) => s.hospital_id === tenant.id) ?? null;

  // Real Plan.capabilities preview (admin/plans_api.py / useAdminPlans) --
  // distinct from `includedInPlan` above, which is the hardcoded hospital/
  // clinic tenant_type default "Reset to Plan Defaults" still uses. Plans
  // are meant to drive admin_capabilities (see Plan's own docstring in
  // orm_models.py) but nothing wires that up yet -- this preview + apply
  // control is that wiring. Always the hospital's OWN assigned plan
  // (subscription.plan_id) -- no manual plan picker, so there's nothing to
  // get out of sync with what /admin/subscriptions actually has assigned.
  const assignedPlan = plans?.find((p) => p.id === subscription?.plan_id) ?? null;

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
          label="Active Subscriptions"
          value={activeSubscriptionsCount}
          deltaPct={null}
          hint={
            activeSubscriptionsCount !== null
              ? `${Math.round((activeSubscriptionsCount / Math.max(tenants.length, 1)) * 100)}% of total hospitals`
              : "Loading…"
          }
          icon={FileText}
        />
        <StatTile
          label="Custom Access Profiles"
          value={customCount}
          deltaPct={null}
          hint="Role-based configurations"
          icon={Users}
          tint="success"
        />
        <StatTile
          label="Expiring This Month"
          value={expiringThisMonthCount}
          deltaPct={null}
          hint="Require renewal action"
          icon={Clock}
          tint="clay"
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
              <p className="text-hint mb-space-1">Configuration Status</p>
              <Badge tone={isCustom ? "clay" : "success"}>
                {isCustom ? "Custom Configuration" : "Default Configuration"}
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

      <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card className="p-space-4">
            <div className="mb-space-3 gap-space-3 flex flex-wrap items-start justify-between">
              <div>
                <h3 className="text-label text-ink-900 font-bold">Portal Management Access</h3>
                <p className="text-hint mt-space-1">
                  Configure which staff-portal management screens are enabled for this hospital.
                </p>
              </div>
              <button
                type="button"
                onClick={resetCapabilitiesToDefaults}
                className="text-brand-600 gap-space-1 flex items-center text-[12.5px] font-semibold hover:underline"
              >
                <RotateCcw size={13} /> Reset to Plan Defaults
              </button>
            </div>

            <DataTable<CapabilityRow>
              columns={createAccessControlColumns({ onToggle: toggleCapability })}
              data={tenant.all_capabilities.map((key) => {
                const meta = CAPABILITY_META[key] || { label: key, icon: Settings };
                return {
                  key,
                  label: meta.label,
                  icon: meta.icon,
                  enabled: form.admin_capabilities.includes(key),
                  inPlan: includedInPlan.includes(key),
                };
              })}
              getRowId={(row) => row.key}
              pageSize={25}
            />
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <PanelHeader
              title="Plan Capabilities"
              subtitle="This hospital's assigned plan and the capabilities it includes."
            />
            {!plans || !subscriptions ? (
              <p className="text-ink-400 text-[12.5px]">Loading…</p>
            ) : !subscription?.plan_id ? (
              <p className="text-ink-400 text-[12.5px]">
                No plan assigned yet —{" "}
                <a href="/admin/subscriptions" className="text-brand-600 hover:underline">
                  assign one
                </a>
                .
              </p>
            ) : assignedPlan ? (
              <div>
                <p className="text-hint mb-space-2">
                  <span className="text-ink-900 font-semibold">{assignedPlan.name}</span> allows{" "}
                  {assignedPlan.capabilities.length} of {tenant.all_capabilities.length}{" "}
                  capabilities — {form.admin_capabilities.length} currently active
                </p>
                <div className="gap-space-1 mb-space-3 flex flex-wrap">
                  {tenant.all_capabilities.map((key) => {
                    // Greyed whenever this hospital doesn't currently have it
                    // switched on (form.admin_capabilities) -- NOT just
                    // whether the plan allows it, so this can't show "16 of
                    // 16" all green while the table right next to it shows 2
                    // of those same capabilities toggled off (a custom
                    // override). Plan membership is what "Apply to This
                    // Hospital" below would turn on, not what's on now.
                    const active = form.admin_capabilities.includes(key);
                    const inPlanAtAll = assignedPlan.capabilities.includes(key);
                    const meta = CAPABILITY_META[key] || { label: key, icon: Settings };
                    return (
                      <span
                        key={key}
                        className={cn(
                          "px-space-2 rounded-full py-0.5 text-[11px] font-semibold",
                          active
                            ? "bg-success-tint text-success"
                            : inPlanAtAll
                              ? "bg-clay-100 text-clay-700"
                              : "text-ink-300 bg-black/4 line-through",
                        )}
                      >
                        {meta.label}
                      </span>
                    );
                  })}
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setForm({ ...form, admin_capabilities: assignedPlan.capabilities })
                  }
                  className="text-brand-600 gap-space-1 flex items-center text-[12.5px] font-semibold hover:underline"
                >
                  <ClipboardCheck size={13} /> Apply to This Hospital
                </button>
              </div>
            ) : (
              <p className="text-ink-400 text-[12.5px]">Assigned plan no longer exists.</p>
            )}
          </Card>

          <Card className="p-space-4">
            <PanelHeader title="Subscription Summary" />
            <div className="space-y-space-2 text-[12.5px]">
              <div className="flex items-center justify-between">
                <span className="text-ink-400">Hospital</span>
                <span className="text-ink-900 font-semibold">{tenant.name}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-400">Plan</span>
                <span className="text-ink-900 font-semibold">{subscription?.plan_name ?? "—"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-400">Renewal Date</span>
                <span className="text-ink-900 font-semibold">
                  {subscription?.renewal_date ? formatDate(subscription.renewal_date) : "—"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-400">Users Allowed</span>
                <span className="text-ink-900 font-semibold">
                  {!subscription?.plan_id ? "—" : (subscription.max_users ?? "Unlimited")}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-400">Modules Active</span>
                <span className="text-ink-900 font-semibold">
                  {form.admin_capabilities.length} / {tenant.all_capabilities.length}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-400">WhatsApp Integration</span>
                <Badge tone={tenant.whatsapp_phone_number_id ? "success" : "neutral"}>
                  {tenant.whatsapp_phone_number_id ? "Enabled" : "Disabled"}
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
              subtitle="Common access control actions for the selected hospital."
            />
            <QuickActionList
              size="sm"
              columns={2}
              actions={[
                {
                  label: "Enable All Core Modules",
                  icon: Power,
                  onClick: () => setForm({ ...form, admin_capabilities: tenant.all_capabilities }),
                },
                {
                  label: "Turn Off Staff Access",
                  icon: UserX,
                  onClick: () => toggleCapability("manage_staff", false),
                },
              ]}
            >
              {/* No real backend for either of these yet -- kept full-color
              (not disabled/greyed, per the app's mock convention) with a
              no-op onClick and a "Mock" badge instead. */}
              <div className="relative">
                <QuickActionButton
                  label="Disable Check In / Check Out"
                  icon={Shield}
                  size="sm"
                  onClick={() => {}}
                />
                <Badge tone="clay" className="absolute -top-2 -right-2">
                  Mock
                </Badge>
              </div>
              <div className="relative">
                <QuickActionButton
                  label="Clone Access Profile"
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
            <PanelHeader title="Recent Access Changes" />
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

export default function AccessControlPage() {
  const { tenants, error } = useTenants();
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const activeId = selectedId ?? tenants?.[0]?.id ?? null;

  return (
    <div>
      <div className="mb-space-5">
        <h1 className="text-display">Access Control</h1>
        <p className="text-ink-600 text-[13px]">
          Manage hospital subscriptions, feature access, and menu visibility across client
          hospitals.
        </p>
      </div>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      {!tenants ? (
        <p className="text-ink-400 text-[13px]">Loading…</p>
      ) : tenants.length === 0 ? (
        <p className="text-ink-400 text-[13px]">No hospitals onboarded yet.</p>
      ) : (
        <AccessControlContent
          tenants={tenants}
          selectedId={activeId as number}
          onSelect={setSelectedId}
        />
      )}
    </div>
  );
}
