"use client";

import { useMemo } from "react";
import { Search, Trash2, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { DataTable } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePatients, type Patient } from "@/hooks/usePatients";
import { createPatientColumns } from "./_components/patients-columns";

export default function PortalPatientsPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
  const {
    patients,
    error,
    search,
    setSearch,
    selected,
    toggleSelected,
    toggleSelectAll,
    selectedPatients,
    allSelected,
    pendingDelete,
    setPendingDelete,
    deleting,
    runDelete,
  } = usePatients(ready);

  const columns = useMemo(
    () =>
      createPatientColumns({
        selected, toggleSelected, toggleSelectAll, allSelected,
        onDelete: (p: Patient) => setPendingDelete([p]),
      }),
    [selected, toggleSelected, toggleSelectAll, allSelected, setPendingDelete],
  );

  return (
    <PortalShell hospital={hospital} active="patients">
        <PageHeader title="Patients" />
        {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

        <div className="mb-space-4 flex flex-col gap-space-3 sm:flex-row sm:items-center sm:justify-between sm:gap-space-4">
          <div className="relative w-full flex-1 sm:max-w-[360px]">
            <Search size={15} className="absolute top-1/2 left-space-3 -translate-y-1/2 text-ink-400" />
            <Input
              placeholder="Search by name or phone"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          {selectedPatients.length > 0 && (
            <PermissionGate page="patients" action="delete">
              <Button
                variant="secondary"
                size="md"
                className="border-error/30 text-error hover:border-error hover:bg-error/10"
                onClick={() => setPendingDelete(selectedPatients)}
              >
                <Trash2 size={15} />
                Delete selected ({selectedPatients.length})
              </Button>
            </PermissionGate>
          )}
        </div>

        <Card className="p-space-4">
          {!patients ? (
            <p className="text-[13px] text-ink-400">Loading…</p>
          ) : patients.length === 0 ? (
            <div className="py-space-6 text-center">
              <UserRound size={28} className="mx-auto mb-space-2 text-ink-300" />
              <p className="text-[13px] text-ink-400">
                {search ? "No patients match that search." : "No patients yet — they appear here after a first booking."}
              </p>
            </div>
          ) : (
            <DataTable
              columns={columns}
              data={patients}
              getRowId={(p) => String(p.id)}
              onRowClick={(p) => router.push(`/portal/patients/${p.id}`)}
            />
          )}
        </Card>

        <ConfirmDialog
          open={pendingDelete !== null}
          title={pendingDelete && pendingDelete.length > 1 ? `Delete ${pendingDelete.length} patients?` : "Delete patient?"}
          message={
            pendingDelete
              ? `This will permanently delete ${
                  pendingDelete.length > 1 ? `${pendingDelete.length} patient records` : pendingDelete[0].name || pendingDelete[0].phone
                }. This action is irreversible.`
              : ""
          }
          confirmLabel="Delete"
          destructive
          busy={deleting}
          onConfirm={() => pendingDelete && runDelete(pendingDelete)}
          onCancel={() => setPendingDelete(null)}
        />
    </PortalShell>
  );
}
