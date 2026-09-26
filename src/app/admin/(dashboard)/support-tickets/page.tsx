"use client";

import { useMemo, useState } from "react";
import { CheckCircle2, Clock, ListChecks, PauseCircle, Timer } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { StatTile } from "@/components/portal/StatTile";
import { useAdminSupportTickets } from "@/hooks/useAdminSupportTickets";
import type { SupportTicketRow, TicketStatus } from "@/hooks/useAdminSupportTickets";
import { createSupportTicketColumns } from "./_components/support-ticket-columns";
import { SupportTicketDetailPanel } from "./_components/SupportTicketDetailPanel";
import { CategoryManagementCard } from "./_components/CategoryManagementCard";

type Tab = "all" | TicketStatus;

function matchesTab(row: SupportTicketRow, tab: Tab): boolean {
  if (tab === "all") return true;
  return row.status === tab;
}

function SupportTicketsList() {
  const { tickets, summary, error, setStatus, updatingStatus } = useAdminSupportTickets();

  const [tab, setTab] = useState<Tab>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const rows = useMemo(() => tickets || [], [tickets]);

  const filteredRows = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return rows.filter((t) => {
      if (!matchesTab(t, tab)) return false;
      if (!q) return true;
      return (
        t.subject.toLowerCase().includes(q) ||
        t.hospital_name.toLowerCase().includes(q) ||
        (t.submitted_by_name || "").toLowerCase().includes(q)
      );
    });
  }, [rows, tab, searchQuery]);

  const selected = rows.find((t) => t.id === selectedId) || filteredRows[0] || null;

  const columns = createSupportTicketColumns({ onSelect: (t) => setSelectedId(t.id) });

  const TABS: { key: Tab; label: string }[] = [
    { key: "all", label: `All (${summary?.total ?? 0})` },
    { key: "open", label: `Open (${summary?.open ?? 0})` },
    { key: "in_process", label: `In Process (${summary?.in_process ?? 0})` },
    { key: "on_hold", label: `On Hold (${summary?.on_hold ?? 0})` },
    { key: "completed", label: `Completed (${summary?.completed ?? 0})` },
  ];

  return (
    <div>
      <div className="mb-space-5">
        <h1 className="text-display">Support Tickets</h1>
        <p className="text-ink-600 text-[13px]">
          Every ticket raised by any staff member, across every hospital -- reviewed only here, not
          by a hospital&apos;s own admin.
        </p>
      </div>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      <div className="mb-space-4 gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5">
        <StatTile
          label="Total Tickets"
          value={summary ? summary.total : null}
          deltaPct={null}
          hint="Across all hospitals"
          icon={ListChecks}
        />
        <StatTile
          label="Open"
          value={summary ? summary.open : null}
          deltaPct={null}
          hint="Not started yet"
          icon={Clock}
          tint="clay"
        />
        <StatTile
          label="In Process"
          value={summary ? summary.in_process : null}
          deltaPct={null}
          hint="Being worked on"
          icon={Timer}
        />
        <StatTile
          label="On Hold"
          value={summary ? summary.on_hold : null}
          deltaPct={null}
          hint="Waiting on something"
          icon={PauseCircle}
          tint="error"
        />
        <StatTile
          label="Completed"
          value={summary ? summary.completed : null}
          deltaPct={null}
          hint="Resolved"
          icon={CheckCircle2}
          tint="success"
        />
      </div>

      <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card className="p-space-4">
            {!tickets ? (
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

                <div className="mb-space-3">
                  <input
                    type="text"
                    placeholder="Search by subject, hospital, submitter…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="border-line bg-card px-space-3 text-ink-900 focus:border-brand-400 h-10 w-full rounded-md border text-[13px] outline-none"
                  />
                </div>

                <DataTable
                  columns={columns}
                  data={filteredRows}
                  getRowId={(t) => String(t.id)}
                  onRowClick={(t) => setSelectedId(t.id)}
                  rowClassName={(t) => (t.id === selected?.id ? "bg-brand-50" : "")}
                  pageSize={10}
                  pageSizeOptions={[10, 25, 50]}
                  emptyMessage={
                    rows.length === 0
                      ? "No support tickets yet."
                      : "No tickets match your search/filter."
                  }
                />
              </>
            )}
          </Card>

          <div className="mt-space-4">
            <CategoryManagementCard />
          </div>
        </div>

        <div>
          <SupportTicketDetailPanel
            ticket={selected}
            onStatusChange={setStatus}
            updating={updatingStatus}
          />
        </div>
      </div>
    </div>
  );
}

export default function SupportTicketsPage() {
  return <SupportTicketsList />;
}
