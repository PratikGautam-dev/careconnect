"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/Badge";
import { formatShortDateTime } from "@/lib/formatDate";
import type { Prescription } from "@/hooks/usePharmacyPrescriptions";

export const PRESCRIPTION_STATUS_LABELS: Record<Prescription["status"], string> = {
  draft: "Draft", pending: "Pending", in_progress: "In Progress", completed: "Completed", cancelled: "Cancelled",
};
export const PRESCRIPTION_STATUS_TONES: Record<Prescription["status"], "success" | "clay" | "neutral" | "brand"> = {
  draft: "neutral", pending: "clay", in_progress: "brand", completed: "success", cancelled: "neutral",
};

export function createPrescriptionColumns(): ColumnDef<Prescription>[] {
  return [
    { id: "id", header: "#", cell: ({ row }) => <span className="text-ink-600 font-mono text-[12px]">RX{row.original.id}</span> },
    { id: "patient_name", header: "Patient Name", cell: ({ row }) => <span className="text-ink-900 font-semibold">{row.original.patient_name}</span> },
    { id: "ward_or_opd", header: "Ward/OPD", cell: ({ row }) => <span className="text-ink-600">{row.original.ward_or_opd || "—"}</span> },
    { id: "time", header: "Time", cell: ({ row }) => <span className="text-ink-600">{formatShortDateTime(row.original.created_at)}</span> },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <Badge tone={PRESCRIPTION_STATUS_TONES[row.original.status]}>{PRESCRIPTION_STATUS_LABELS[row.original.status]}</Badge>,
    },
  ];
}
