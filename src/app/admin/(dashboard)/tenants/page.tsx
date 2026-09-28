"use client";

import { useMemo, useState } from "react";
import { Building2, Clock, Hourglass, PauseCircle, Plus, Users } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { StatTile } from "@/components/portal/StatTile";
import { formatDate } from "@/lib/formatDate";
import { useTenants, useTenantProfile, useTenantPaymentSettings, type Tenant } from "@/hooks/useTenants";
import { useAdminSubscriptions } from "@/hooks/useAdminSubscriptions";
import { STATUS_LABEL } from "../subscriptions/_components/subscription-columns";
import { createTenantColumns, TENANT_TYPE_LABELS } from "./_components/tenant-columns";
import { HospitalDetailPanel } from "./_components/HospitalDetailPanel";

// Within this many days of a renewal_date counts as "Expiring Soon" --
// matches the /admin/subscriptions page's own "renewals need attention"
// framing, just windowed to the next 30 days instead of "this calendar
// month" (a renewal_date early next month wouldn't otherwise surface here
// until the month actually turns).
const EXPIRING_SOON_WINDOW_DAYS = 30;

const TYPE_OPTIONS = Object.entries(TENANT_TYPE_LABELS).map(([value, label]) => ({ value, label }));
// unassigned isn't a real per-hospital plan_id -- its own filter value, not
// backed by the plans catalog below.
const SUBSCRIPTION_STATUS_OPTIONS = Object.entries(STATUS_LABEL).map(([value, label]) => ({
  value,
  label,
}));
// Tenant Status -- the hospital account's own is_active toggle (edit-tenant
// page's new Active/Inactive switch), NOT a billing/subscription state.
const TENANT_STATUS_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive" },
];

function TenantsList() {
  const { tenants, stalledSignups, error } = useTenants();
  // Real hospital<->plan assignment (admin/subscriptions_api.py), same data
  // source the /admin/subscriptions page's own stat tiles use -- backs "On
  // Trial"/"Expiring Soon" below instead of the old hardcoded mock numbers.
  const { subscriptions, plans } = useAdminSubscriptions();

  const [selectedHospitalId, setSelectedHospitalId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [planFilter, setPlanFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [subscriptionStatusFilter, setSubscriptionStatusFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const subscriptionByHospitalId = useMemo(
    () => new Map((subscriptions ?? []).map((s) => [s.hospital_id, s])),
    [subscriptions],
  );

  const PLAN_OPTIONS = useMemo(
    () => [
      { value: "unassigned", label: "Unassigned" },
      ...plans.map((p) => ({ value: String(p.id), label: p.name })),
    ],
    [plans],
  );

  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return (tenants ?? []).filter((t) => {
      const sub = subscriptionByHospitalId.get(t.id);
      if (planFilter !== "all") {
        if (planFilter === "unassigned") {
          if (sub?.plan_id != null) return false;
        } else if (String(sub?.plan_id ?? "") !== planFilter) {
          return false;
        }
      }
      if (typeFilter !== "all" && t.tenant_type !== typeFilter) return false;
      if (subscriptionStatusFilter !== "all" && (sub?.status ?? "unassigned") !== subscriptionStatusFilter) {
        return false;
      }
      if (statusFilter !== "all" && (statusFilter === "active") !== t.is_active) return false;
      if (!q) return true;
      return (
        t.name.toLowerCase().includes(q) ||
        (t.contact_address || "").toLowerCase().includes(q) ||
        (t.whatsapp_phone_number_id || "").toLowerCase().includes(q)
      );
    });
  }, [
    tenants,
    searchQuery,
    planFilter,
    typeFilter,
    subscriptionStatusFilter,
    statusFilter,
    subscriptionByHospitalId,
  ]);

  const activeCount = tenants?.filter((t) => t.is_active).length ?? null;
  const totalCount = tenants?.length ?? null;
  // Real hospital-account toggle (edit-tenant's own Active/Inactive
  // switch) -- a tenant an operator has switched off, not a billing state.
  const suspendedCount = tenants?.filter((t) => !t.is_active).length ?? null;
  const onTrialCount = subscriptions?.filter((s) => s.status === "trial").length ?? null;
  const now = new Date();
  const expiringSoonCount =
    subscriptions?.filter((s) => {
      if (!s.renewal_date) return false;
      const daysUntil =
        (new Date(s.renewal_date).getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
      return daysUntil >= 0 && daysUntil <= EXPIRING_SOON_WINDOW_DAYS;
    }).length ?? null;

  // Default-first-row-selected master-detail, same convention as
  // Staff/Billing's own detail panels.
  const selectedHospital =
    (tenants ?? []).find((t) => t.id === selectedHospitalId) || filtered[0] || null;
  const selectedSubscription =
    subscriptions?.find((s) => s.hospital_id === selectedHospital?.id) ?? null;
  const selectedProfile = useTenantProfile(selectedHospital?.id ?? null);
  const selectedPaymentSettings = useTenantPaymentSettings(selectedHospital?.id ?? null);

  const planNameByHospitalId = useMemo(
    () => new Map((subscriptions ?? []).map((s) => [s.hospital_id, s.plan_name])),
    [subscriptions],
  );

  const columns = createTenantColumns({ planNameByHospitalId });

  return (
    <div>
      <div className="mb-space-5 gap-space-3 flex flex-col items-start sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-display">Tenants</h1>
          <p className="text-ink-600 text-[13px]">
            Manage hospital &amp; clinic tenant accounts, view subscription status, and oversee
            onboarding across the platform.
          </p>
        </div>
        <Button href="/admin/onboard-hospital" variant="primary">
          <Plus size={16} /> Add New Hospital
        </Button>
      </div>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      <div className="mb-space-4 gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5">
        <StatTile
          label="Total Hospitals"
          value={totalCount}
          deltaPct={null}
          hint="Across all subscriptions"
          icon={Building2}
        />
        <StatTile
          label="Active Hospitals"
          value={activeCount}
          deltaPct={null}
          hint={
            totalCount
              ? `${Math.round(((activeCount ?? 0) / totalCount) * 100)}% of total hospitals`
              : "Loading…"
          }
          icon={Users}
          tint="success"
        />
        <StatTile
          label="On Trial"
          value={onTrialCount}
          deltaPct={null}
          hint={
            totalCount
              ? `${Math.round(((onTrialCount ?? 0) / totalCount) * 100)}% of total hospitals`
              : "Loading…"
          }
          icon={Hourglass}
          tint="clay"
        />
        <StatTile
          label="Suspended"
          value={suspendedCount}
          deltaPct={null}
          hint={
            totalCount
              ? `${Math.round(((suspendedCount ?? 0) / totalCount) * 100)}% of total hospitals`
              : "Loading…"
          }
          icon={PauseCircle}
          tint="error"
        />
        <StatTile
          label="Expiring Soon"
          value={expiringSoonCount}
          deltaPct={null}
          hint={`Within next ${EXPIRING_SOON_WINDOW_DAYS} days`}
          icon={Clock}
          tint="clay"
        />
      </div>

      <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card className="p-space-4">
            <div className="mb-space-3 gap-space-3 flex flex-wrap items-start justify-between">
              <div>
                <h3 className="text-label text-ink-900 font-bold">Hospital Directory</h3>
                <p className="text-hint mt-space-1">
                  View and manage all client hospitals, their subscription status and onboarding
                  progress.
                </p>
              </div>
            </div>

            <div className="mb-space-3 gap-space-3 flex flex-wrap items-center">
              <div className="relative min-w-50 flex-1">
                <input
                  type="text"
                  placeholder="Search hospitals, location or WhatsApp number…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="border-line bg-card px-space-3 text-ink-900 focus:border-brand-400 h-10 w-full rounded-md border text-[13px] outline-none"
                />
              </div>
              <FilterSelect
                value={planFilter}
                onChange={setPlanFilter}
                allLabel="All Plans"
                options={PLAN_OPTIONS}
              />
              <FilterSelect
                value={typeFilter}
                onChange={setTypeFilter}
                allLabel="All Tenant Types"
                options={TYPE_OPTIONS}
              />
              <FilterSelect
                value={subscriptionStatusFilter}
                onChange={setSubscriptionStatusFilter}
                allLabel="All Subscription Statuses"
                options={SUBSCRIPTION_STATUS_OPTIONS}
              />
              <FilterSelect
                value={statusFilter}
                onChange={setStatusFilter}
                allLabel="All Tenant Statuses"
                options={TENANT_STATUS_OPTIONS}
              />
            </div>

            <DataTable<Tenant>
              columns={columns}
              data={filtered}
              getRowId={(t) => String(t.id)}
              onRowClick={(t) => setSelectedHospitalId(t.id)}
              rowClassName={(t) => (t.id === selectedHospital?.id ? "bg-brand-50" : "")}
              pageSize={10}
              pageSizeOptions={[10, 25, 50]}
              loading={!tenants}
              emptyMessage={
                tenants && tenants.length > 0
                  ? "No hospitals match your search/filters."
                  : "No tenants onboarded yet."
              }
            />
          </Card>
        </div>

        <div>
          <HospitalDetailPanel
            hospital={selectedHospital}
            subscription={selectedSubscription}
            profile={selectedProfile}
            paymentSettings={selectedPaymentSettings}
          />
        </div>
      </div>

      <div className="mt-space-7 mb-space-3">
        <h2 className="text-display !text-[20px]">Signed in, never onboarded</h2>
        <p className="text-ink-600 text-[13px]">
          Google accounts that have signed in but don&apos;t own a hospital yet.
        </p>
      </div>
      <Card className="p-space-4">
        {!stalledSignups ? (
          <p className="py-space-4 text-ink-400 text-center text-[13px]">Loading…</p>
        ) : stalledSignups.length === 0 ? (
          <p className="py-space-4 text-ink-400 text-center text-[13px]">
            Nobody — every signed-in account owns at least one hospital.
          </p>
        ) : (
          <ul className="divide-line divide-y">
            {stalledSignups.map((u) => (
              <li
                key={u.id}
                className="gap-space-1 py-space-3 flex flex-col sm:flex-row sm:items-center sm:justify-between sm:gap-0"
              >
                <div>
                  <p className="text-ink-900 text-[13.5px] font-semibold">{u.name || u.email}</p>
                  {u.name && <p className="text-ink-600 text-[12px]">{u.email}</p>}
                </div>
                <span className="text-ink-400 text-[12px]">
                  Signed in {formatDate(u.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export default function TenantsPage() {
  return <TenantsList />;
}
