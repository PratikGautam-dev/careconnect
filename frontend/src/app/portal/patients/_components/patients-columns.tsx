"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { formatDate } from "@/lib/formatDate";
import type { Patient } from "@/hooks/usePatients";
import { PatientCellAction } from "./patients-cellaction";

type CreatePatientColumnsOptions = {
  selected: Set<number>;
  toggleSelected: (id: number, checked: boolean) => void;
  toggleSelectAll: (checked: boolean) => void;
  allSelected: boolean;
  onDelete: (patient: Patient) => void;
};

/** Column definitions for the /portal/patients DataTable. The row itself is
 * clickable (DataTable's onRowClick, navigates to /portal/patients/[id]);
 * the checkbox and actions-menu cells stop propagation so clicking them
 * doesn't also trigger that navigation. View Details/Delete are combined
 * into one trailing actions menu (PatientCellAction) rather than two
 * separate columns. */
export function createPatientColumns({
  selected, toggleSelected, toggleSelectAll, allSelected, onDelete,
}: CreatePatientColumnsOptions): ColumnDef<Patient>[] {
  return [
    {
      id: "select",
      header: () => (
        <input
          type="checkbox"
          checked={allSelected}
          onChange={(e) => toggleSelectAll(e.target.checked)}
          onClick={(e) => e.stopPropagation()}
          className="h-4 w-4 accent-brand-600"
          aria-label="Select all patients"
        />
      ),
      cell: ({ row }) => {
        const p = row.original;
        return (
          <input
            type="checkbox"
            checked={selected.has(p.id)}
            onChange={(e) => toggleSelected(p.id, e.target.checked)}
            onClick={(e) => e.stopPropagation()}
            className="h-4 w-4 accent-brand-600"
            aria-label={`Select ${p.name || p.phone}`}
          />
        );
      },
    },
    {
      id: "patient_display_id",
      header: "Patient ID",
      cell: ({ row }) => (
        <span className="whitespace-nowrap font-mono text-[12px] text-ink-600">
          {row.original.patient_display_id || `#${row.original.id}`}
        </span>
      ),
    },
    {
      id: "mrn",
      header: "MRN",
      cell: ({ row }) => <span className="whitespace-nowrap font-mono text-[12px] text-ink-600">{row.original.mrn || "—"}</span>,
    },
    {
      id: "name",
      header: "Name",
      cell: ({ row }) => (
        <Link
          href={`/portal/patients/${row.original.id}`}
          onClick={(e) => e.stopPropagation()}
          className="font-semibold text-ink-900 hover:underline"
        >
          {row.original.name || "—"}
        </Link>
      ),
    },
    {
      id: "phone",
      header: "Phone",
      cell: ({ row }) => <span className="text-ink-600">{row.original.phone}</span>,
    },
    {
      id: "last_visit",
      header: "Last visit",
      cell: ({ row }) => <span className="text-ink-600">{formatDate(row.original.last_visit)}</span>,
    },
    {
      id: "visit_count",
      header: "Booked",
      cell: ({ row }) => <span className="tabular-nums text-ink-600">{row.original.visit_count}</span>,
    },
    {
      id: "visited_count",
      header: "Visited",
      cell: ({ row }) => <span className="tabular-nums text-ink-600">{row.original.visited_count}</span>,
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <div className="text-right">
          <PatientCellAction patient={row.original} onDelete={onDelete} />
        </div>
      ),
    },
  ];
}
