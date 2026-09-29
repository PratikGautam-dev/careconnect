"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { Field } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useRefunds } from "@/hooks/useRefunds";
import { createRefundColumns } from "./refunds-columns";

/** Billing -> Refunds tab: the cancel/refund approval queue for a hospital
 * that turned Settings -> Appointments' "Auto-approve refunds" off. Only
 * makes sense to show/act on when the hospital actually has that switch
 * off, but this component doesn't gate on that itself -- an already-empty
 * pending queue (the common case for an auto-refund hospital) reads fine on
 * its own ("No refunds pending approval."). */
export function RefundsQueue({ canWrite }: { canWrite: boolean }) {
  const {
    refunds,
    error,
    isFetching,
    selected,
    toggleSelected,
    toggleSelectAll,
    approve,
    approvingId,
    reject,
    rejectingId,
    sync,
    syncingId,
    bulkApprove,
    bulkApproving,
  } = useRefunds(true, "pending_approval");

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [rangeError, setRangeError] = useState<string | null>(null);

  const pendingCount = refunds.filter((r) => r.status === "pending_approval").length;
  const allSelected = pendingCount > 0 && selected.size === pendingCount;

  function handleReject(id: number) {
    const reason = window.prompt("Reason for rejecting this refund (optional):", "") ?? undefined;
    reject({ id, reason });
  }

  async function handleBulkApproveSelected() {
    await bulkApprove({ refund_request_ids: [...selected] });
  }

  async function handleBulkApproveByRange() {
    if (!dateFrom || !dateTo) {
      setRangeError("Pick both a from and to date.");
      return;
    }
    if (dateTo < dateFrom) {
      setRangeError('"To" must be on or after "From".');
      return;
    }
    setRangeError(null);
    await bulkApprove({ date_from: dateFrom, date_to: dateTo });
    setDateFrom("");
    setDateTo("");
  }

  return (
    <div className="gap-space-4 flex flex-col">
      {error && <p className="text-error text-[13px]">{error}</p>}

      {canWrite && (
        <Card className="p-space-4">
          <h3 className="text-label text-ink-900 mb-space-1 font-bold">
            Approve by appointment date range
          </h3>
          <p className="text-hint mb-space-3">
            Approves and processes every pending refund whose cancelled appointment falls in this
            range -- useful for clearing a backlog in one go.
          </p>
          <div className="gap-space-3 flex flex-wrap items-center">
            <Field label="From" className="mb-0" error={rangeError || undefined}>
              <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            </Field>
            <Field label="To" className="mb-0">
              <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </Field>
            <Button onClick={handleBulkApproveByRange} disabled={bulkApproving}>
              {bulkApproving ? "Approving…" : "Approve range"}
            </Button>
          </div>
        </Card>
      )}

      <Card className="p-space-4">
        <div className="mb-space-3 gap-space-3 flex flex-wrap items-center justify-between">
          <div>
            <h3 className="text-label text-ink-900 font-bold">Pending approval</h3>
            <p className="text-hint mt-space-1">Refunds waiting for a staff decision.</p>
          </div>
          {canWrite && selected.size > 0 && (
            <Button onClick={handleBulkApproveSelected} disabled={bulkApproving}>
              {bulkApproving ? "Approving…" : `Approve ${selected.size} selected`}
            </Button>
          )}
        </div>

        <DataTable
          columns={createRefundColumns({
            canWrite,
            selected,
            toggleSelected,
            toggleSelectAll,
            allSelected,
            selectableCount: pendingCount,
            approvingId,
            rejectingId,
            syncingId,
            onApprove: approve,
            onReject: handleReject,
            onSync: sync,
          })}
          data={refunds}
          getRowId={(r) => String(r.id)}
          pageSize={10}
          pageSizeOptions={[10, 25, 50]}
          loading={isFetching && refunds.length === 0}
          emptyMessage="No refunds pending approval."
        />
      </Card>
    </div>
  );
}
