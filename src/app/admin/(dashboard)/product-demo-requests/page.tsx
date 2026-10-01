"use client";

import { useMemo, useState } from "react";
import { CalendarClock, CheckCircle2, ListChecks, MailPlus, PhoneCall } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { useAdminProductDemoRequests } from "@/hooks/useAdminProductDemoRequests";
import type { DemoRequestStatus, ProductDemoRequestRow } from "@/hooks/useAdminProductDemoRequests";
import { createDemoRequestColumns } from "./_components/demo-request-columns";
import { DemoRequestDetailPanel } from "./_components/DemoRequestDetailPanel";

type Tab = "all" | DemoRequestStatus;

function matchesTab(row: ProductDemoRequestRow, tab: Tab): boolean {
  if (tab === "all") return true;
  return row.status === tab;
}

function ProductDemoRequestsList() {
  const { requests, summary, error, setStatus, updatingStatus } = useAdminProductDemoRequests();

  const [tab, setTab] = useState<Tab>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const rows = useMemo(() => requests || [], [requests]);

  const filteredRows = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return rows.filter((r) => {
      if (!matchesTab(r, tab)) return false;
      if (!q) return true;
      return (
        r.name.toLowerCase().includes(q) ||
        r.email.toLowerCase().includes(q) ||
        (r.hospital_name || "").toLowerCase().includes(q)
      );
    });
  }, [rows, tab, searchQuery]);

  const selected = rows.find((r) => r.id === selectedId) || filteredRows[0] || null;

  const columns = createDemoRequestColumns({ onSelect: (r) => setSelectedId(r.id) });

  const TABS: { key: Tab; label: string }[] = [
    { key: "all", label: `All (${summary?.total ?? 0})` },
    { key: "new", label: `New (${summary?.new ?? 0})` },
    { key: "contacted", label: `Contacted (${summary?.contacted ?? 0})` },
    { key: "scheduled", label: `Scheduled (${summary?.scheduled ?? 0})` },
    { key: "closed", label: `Closed (${summary?.closed ?? 0})` },
  ];

  return (
    <div>
      <div className="mb-space-5">
        <h1 className="text-display">Product Demo Requests</h1>
        <p className="text-ink-600 text-[13px]">
          Every &quot;Request a product demo&quot; submission from the public landing page.
        </p>
      </div>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      <StatTileGrid cols={5} className="mb-space-4">
        <StatTile label="Total Requests" value={summary ? summary.total : null} icon={ListChecks} />
        <StatTile label="New" value={summary ? summary.new : null} icon={MailPlus} tint="clay" />
        <StatTile label="Contacted" value={summary ? summary.contacted : null} icon={PhoneCall} />
        <StatTile
          label="Scheduled"
          value={summary ? summary.scheduled : null}
          icon={CalendarClock}
          tint="success"
        />
        <StatTile label="Closed" value={summary ? summary.closed : null} icon={CheckCircle2} />
      </StatTileGrid>

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

                <div className="mb-space-3">
                  <input
                    type="text"
                    placeholder="Search by name, email, hospital…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="border-line bg-card px-space-3 text-ink-900 focus:border-brand-400 h-10 w-full rounded-md border text-[13px] outline-none"
                  />
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
                      ? "No demo requests yet."
                      : "No requests match your search/filter."
                  }
                />
              </>
            )}
          </Card>
        </div>

        <div>
          <DemoRequestDetailPanel
            request={selected}
            onStatusChange={setStatus}
            updating={updatingStatus}
          />
        </div>
      </div>
    </div>
  );
}

export default function ProductDemoRequestsPage() {
  return <ProductDemoRequestsList />;
}
