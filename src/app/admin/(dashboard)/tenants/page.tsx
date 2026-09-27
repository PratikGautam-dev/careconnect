"use client";

import { useMemo, useState } from "react";
import { Building2, Clock, Hourglass, PauseCircle, Plus, Users } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { StatTile } from "@/components/portal/StatTile";
import { formatDate } from "@/lib/formatDate";
import { useTenants, useTenantProfile, type Tenant } from "@/hooks/useTenants";
import { useAdminSubscriptions } from "@/hooks/useAdminSubscriptions";
import { createTenantColumns, TIER_LABELS } from "./_components/tenant-columns";
import { HospitalDetailPanel } from "./_components/HospitalDetailPanel";

// Within this many days of a renewal_date counts as "Expiring Soon" --
// matches the /admin/subscriptions page's own "renewals need attention"
// framing, just windowed to the next 30 days instead of "this calendar
// month" (a renewal_date early next month wouldn't otherwise surface here
// until the month actually turns).
const EXPIRING_SOON_WINDOW_DAYS = 30;

const TIER_OPTIONS = Object.entries(TIER_LABELS).map(([value, label]) => ({ value, label }));
const STATUS_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive" },
];

function TenantsList() {
  const { tenants, stalledSignups, error } = useTenants();
  // Real hospital<->plan assignment (admin/subscriptions_api.py), same data
  // source the /admin/subscriptions page's own stat tiles use -- backs "On
  // Trial"/"Expiring Soon" below instead of the old hardcoded mock numbers.
  const { subscriptions } = useAdminSubscriptions();

  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [selectedHospitalId, setSelectedHospitalId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [tierFilter, setTierFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return (tenants ?? []).filter((t) => {
      if (tierFilter !== "all" && t.data_tier !== tierFilter) return false;
      if (statusFilter !== "all" && (statusFilter === "active") !== t.is_active) return false;
      if (!q) return true;
      return (
        t.name.toLowerCase().includes(q) ||
        (t.contact_address || "").toLowerCase().includes(q) ||
        (t.whatsapp_phone_number_id || "").toLowerCase().includes(q)
      );
    });
  }, [tenants, searchQuery, tierFilter, statusFilter]);

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

  function toggleOne(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll(checked: boolean) {
    setSelectedIds(checked ? new Set(filtered.map((t) => t.id)) : new Set());
  }

  const columns = createTenantColumns({
    selectedIds,
    onToggle: toggleOne,
    onToggleAll: toggleAll,
    allSelected: filtered.length > 0 && filtered.every((t) => selectedIds.has(t.id)),
  });

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
                value={tierFilter}
                onChange={setTierFilter}
                allLabel="All Plans"
                options={TIER_OPTIONS}
              />
              <FilterSelect
                value={statusFilter}
                onChange={setStatusFilter}
                allLabel="All Statuses"
                options={STATUS_OPTIONS}
              />
            </div>

            {selectedIds.size > 0 && (
              <p className="text-brand-700 bg-brand-50 px-space-3 py-space-2 mb-space-3 rounded-md text-[12.5px] font-semibold">
                {selectedIds.size} selected
              </p>
            )}

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
