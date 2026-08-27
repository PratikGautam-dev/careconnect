"use client";

import { ChevronRight, Search, Trash2, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input } from "@/components/ui/Input";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePatients } from "@/hooks/usePatients";

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

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

  return (
    <PortalShell hospital={hospital} active="patients">
        <h1 className="text-display mb-space-5">Patients</h1>
        {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

        <div className="mb-space-4 flex items-center justify-between gap-space-4">
          <div className="relative max-w-[360px] flex-1">
            <Search size={15} className="absolute top-1/2 left-space-3 -translate-y-1/2 text-ink-400" />
            <Input
              placeholder="Search by name or phone"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          {selectedPatients.length > 0 && (
            <Button
              variant="secondary"
              size="md"
              className="border-error/30 text-error hover:border-error hover:bg-error/10"
              onClick={() => setPendingDelete(selectedPatients)}
            >
              <Trash2 size={15} />
              Delete selected ({selectedPatients.length})
            </Button>
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
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[13px]">
                <thead>
                  <tr className="border-b border-line text-[11.5px] text-ink-400 uppercase">
                    <th className="w-8 pb-space-2 font-semibold">
                      <input
                        type="checkbox"
                        checked={allSelected}
                        onChange={(e) => toggleSelectAll(e.target.checked)}
                        onClick={(e) => e.stopPropagation()}
                        className="h-4 w-4 accent-brand-600"
                        aria-label="Select all patients"
                      />
                    </th>
                    <th className="pb-space-2 font-semibold">Patient ID</th>
                    <th className="pb-space-2 font-semibold">MRN</th>
                    <th className="pb-space-2 font-semibold">Name</th>
                    <th className="pb-space-2 font-semibold">Phone</th>
                    <th className="pb-space-2 font-semibold">Last visit</th>
                    <th className="pb-space-2 font-semibold">Visits</th>
                    <th className="pb-space-2 font-semibold"></th>
                    <th className="pb-space-2 font-semibold"></th>
                  </tr>
                </thead>
                <tbody>
                  {patients.map((p) => (
                    <tr
                      key={p.id}
                      onClick={() => router.push(`/portal/patients/${p.id}`)}
                      className="cursor-pointer border-b border-line last:border-0 hover:bg-black/[0.02]"
                    >
                      <td className="py-space-2" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selected.has(p.id)}
                          onChange={(e) => toggleSelected(p.id, e.target.checked)}
                          className="h-4 w-4 accent-brand-600"
                          aria-label={`Select ${p.name || p.phone}`}
                        />
                      </td>
                      <td className="py-space-2 whitespace-nowrap font-mono text-[12px] text-ink-600">
                        {p.patient_display_id || `#${p.id}`}
                      </td>
                      <td className="py-space-2 whitespace-nowrap font-mono text-[12px] text-ink-600">
                        {p.mrn || "—"}
                      </td>
                      <td className="py-space-2 font-semibold text-ink-900">
                        <Link href={`/portal/patients/${p.id}`} className="hover:underline">
                          {p.name || "—"}
                        </Link>
                      </td>
                      <td className="py-space-2 text-ink-600">{p.phone}</td>
                      <td className="py-space-2 text-ink-600">{formatDate(p.last_visit)}</td>
                      <td className="py-space-2 tabular-nums text-ink-600">{p.visit_count}</td>
                      <td className="py-space-2 text-right">
                        <span className="inline-flex items-center gap-0.5 text-[12px] font-semibold text-brand-600">
                          View <ChevronRight size={14} />
                        </span>
                      </td>
                      <td className="py-space-2 text-right" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          onClick={() => setPendingDelete([p])}
                          className="rounded p-1 text-ink-400 hover:bg-error/10 hover:text-error"
                          aria-label={`Delete ${p.name || p.phone}`}
                        >
                          <Trash2 size={15} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
