"use client";

import { useMemo, useState } from "react";
import {
  CalendarCheck,
  CalendarX,
  Clock,
  ListChecks,
  Plus,
  Search,
  SlidersHorizontal,
  UserRound,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { NewLeaveRequestDialog } from "@/components/portal/NewLeaveRequestDialog";
import { PortalShell } from "@/components/portal/PortalShell";
import { PortalTopBarActions } from "@/components/portal/PortalTopBarActions";
import { StatTile } from "@/components/portal/StatTile";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePermission } from "@/lib/staffAuth";
import { formatHeaderDate } from "@/lib/formatDate";
import { useLeaveRequests, type LeaveRequestRow } from "@/hooks/useLeaveRequests";
import { createLeaveRequestColumns } from "./_components/leave-request-columns";
import { LeaveRequestDetailPanel } from "./_components/LeaveRequestDetailPanel";

type Tab = "all" | "doctor" | "staff" | "pending" | "approved" | "rejected";

/** Not a real staff role -- "staff" here means "not a doctor" (admin +
 * receptionist), matching the mockup's own Doctors(14)/Staff(22) tab split
 * -- a role-family filter, distinct from the pending/approved/rejected
 * status filters that sit alongside it in the same tab row. */
function matchesTab(row: LeaveRequestRow, tab: Tab): boolean {
  if (tab === "all") return true;
  if (tab === "doctor") return row.is_doctor_role;
  if (tab === "staff") return !row.is_doctor_role;
  return row.status === tab;
}

export default function LeaveRequestsPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("leave_requests", "view");
  const canManage = usePermission("leave_requests", "write");
  const { requests, summary, error, decidingId, approve, reject, load } = useLeaveRequests(
    ready && canView,
  );

  const [tab, setTab] = useState<Tab>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [newRequestOpen, setNewRequestOpen] = useState(false);

  const today = new Date();
  const rows = useMemo(() => requests || [], [requests]);

  const filteredRows = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return rows.filter((r) => {
      if (!matchesTab(r, tab)) return false;
      if (!q) return true;
      return (
        r.applicant_name.toLowerCase().includes(q) ||
        (r.department_name || "").toLowerCase().includes(q)
      );
    });
  }, [rows, tab, searchQuery]);

  // Falls back to the first (most recent -- the backend already sorts
  // newest first) row whenever nothing's been explicitly clicked yet, so
  // the detail panel shows something instead of its own empty "Select a
  // leave request" state on first load. A derived fallback rather than an
  // effect that syncs selectedId itself -- once the admin clicks a row,
  // selectedId is set for real and this only matters again if THAT row
  // stops matching (e.g. a search/tab filter hides it).
  const selected = rows.find((r) => r.id === selectedId) || rows[0] || null;
  const doctorCount = rows.filter((r) => r.is_doctor_role).length;
  const staffCount = rows.filter((r) => !r.is_doctor_role).length;

  const columns = createLeaveRequestColumns({
    onSelect: (r) => setSelectedId(r.id),
    canManage,
    decidingId,
    onApprove: approve,
    onReject: reject,
  });

  const TABS: { key: Tab; label: string }[] = [
    { key: "all", label: `All (${rows.length})` },
    { key: "doctor", label: `Doctors (${doctorCount})` },
    { key: "staff", label: `Staff (${staffCount})` },
    { key: "pending", label: `Pending (${summary?.pending ?? 0})` },
    { key: "approved", label: `Approved (${summary?.approved ?? 0})` },
    { key: "rejected", label: `Rejected (${summary?.rejected ?? 0})` },
  ];

  return (
    <PortalShell hospital={hospital} active="leave-requests">
      <PageHeader
        title="Leave requests"
        description={formatHeaderDate(today)}
        actions={
          <>
            {canManage && (
              <Button type="button" onClick={() => setNewRequestOpen(true)}>
                <Plus size={14} /> New leave request
              </Button>
            )}
            <PortalTopBarActions />
          </>
        }
      />

      {canManage && (
        <NewLeaveRequestDialog
          open={newRequestOpen}
          onOpenChange={setNewRequestOpen}
          onCreated={load}
        />
      )}

      {!ready || !canView ? (
        !ready ? null : (
          <p className="text-ink-400 text-[13px]">You don&apos;t have access to Leave Requests.</p>
        )
      ) : (
        <>
          {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

          <div className="mb-space-4 gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5">
            <StatTile
              label="Total Requests"
              value={summary ? summary.total : null}
              deltaPct={null}
              hint="Live count"
              icon={ListChecks}
            />
            <StatTile
              label="Pending Approval"
              value={summary ? summary.pending : null}
              deltaPct={null}
              hint="Needs review"
              icon={Clock}
              tint="clay"
            />
            <StatTile
              label="Approved"
              value={summary ? summary.approved : null}
              deltaPct={null}
              hint="Live count"
              icon={CalendarCheck}
            />
            <StatTile
              label="Rejected"
              value={summary ? summary.rejected : null}
              deltaPct={null}
              hint="Live count"
              icon={CalendarX}
            />
            <StatTile
              label="On Leave Today"
              value={summary ? summary.on_leave_today : null}
              deltaPct={null}
              hint="Approved, today"
              icon={UserRound}
            />
          </div>

          <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
            <div className="lg:col-span-2">
              <Card className="p-space-4">
                {!requests ? (
                  <p className="text-ink-400 text-[13px]">Loading…</p>
                ) : (
                  <>
                    <div className="mb-space-3 gap-space-1 flex flex-wrap">
                      {TABS.map((t) => (
                        <button
                          key={t.key}
                          type="button"
                          onClick={() => setTab(t.key)}
                          className={
                            "px-space-3 py-space-1.5 rounded-md text-[12.5px] font-semibold transition-colors " +
                            (tab === t.key
                              ? "bg-brand-600 text-white"
                              : "text-ink-600 bg-black/4 hover:bg-black/8")
                          }
                        >
                          {t.label}
                        </button>
                      ))}
                    </div>

                    <div className="mb-space-3 gap-space-3 flex flex-wrap items-center">
                      <div className="relative min-w-50 flex-1">
                        <Search
                          size={14}
                          className="left-space-3 text-ink-400 pointer-events-none absolute top-1/2 -translate-y-1/2"
                        />
                        <input
                          type="text"
                          placeholder="Search by name, department…"
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          className="border-line bg-card pl-space-8 pr-space-3 text-ink-900 focus:border-brand-400 h-10 w-full rounded-md border text-[13px] outline-none"
                        />
                      </div>
                      <Button type="button" variant="secondary" disabled title="Coming soon">
                        <SlidersHorizontal size={14} /> Filters
                      </Button>
                    </div>

                    <DataTable
                      columns={columns}
                      data={filteredRows}
                      getRowId={(r) => String(r.id)}
                      onRowClick={(r) => setSelectedId(r.id)}
                      rowClassName={(r) => (r.id === selected?.id ? "bg-brand-50" : "")}
                      pageSize={10}
                      pageSizeOptions={[10, 25, 50]}
                      emptyMessage={
                        rows.length === 0
                          ? "No leave requests yet."
                          : "No requests match your search/filter."
                      }
                    />
                  </>
                )}
              </Card>
            </div>

            <div>
              <LeaveRequestDetailPanel
                request={selected}
                canManage={canManage}
                decidingId={decidingId}
                onApprove={approve}
                onReject={reject}
              />
            </div>
          </div>
        </>
      )}
    </PortalShell>
  );
}
