"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { formatShortDateTime } from "@/lib/formatDate";
import type { Prescription } from "@/hooks/usePharmacyPrescriptions";
import { PRESCRIPTION_STATUS_LABELS, PRESCRIPTION_STATUS_TONES } from "../prescriptions/_components/prescriptions-columns";

type QueueTab = "pending" | "in_progress" | "completed";

const TABS: { key: QueueTab; label: string }[] = [
  { key: "pending", label: "Pending" },
  { key: "in_progress", label: "In Progress" },
  { key: "completed", label: "Completed" },
];

export function PrescriptionQueueCard({ prescriptions }: { prescriptions: Prescription[] }) {
  const router = useRouter();
  const [tab, setTab] = useState<QueueTab>("pending");
  const counts = {
    pending: prescriptions.filter((p) => p.status === "pending").length,
    in_progress: prescriptions.filter((p) => p.status === "in_progress").length,
    completed: prescriptions.filter((p) => p.status === "completed").length,
  };
  const rows = prescriptions.filter((p) => p.status === tab).slice(0, 8);

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex items-center justify-between">
        <h3 className="text-label text-ink-900 font-bold">Prescription Queue</h3>
        <Link href="/portal/pharmacy/prescriptions" className="text-brand-600 text-[12px] font-semibold">View All</Link>
      </div>
      <div className="gap-space-2 mb-space-3 flex">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              "px-space-3 py-space-1 rounded-full text-[12px] font-semibold transition-colors duration-150",
              tab === t.key ? "bg-brand-600 text-white" : "bg-black/4 text-ink-600 hover:bg-black/6",
            )}
          >
            {t.label} ({counts[t.key]})
          </button>
        ))}
      </div>
      <div className="space-y-space-1 max-h-72 overflow-y-auto">
        {rows.length === 0 && <p className="text-hint py-space-4 text-center text-[12.5px]">No prescriptions here.</p>}
        {rows.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => router.push(`/portal/pharmacy/prescriptions/${p.id}`)}
            className="px-space-2 py-space-2 hover:bg-black/4 flex w-full items-center justify-between rounded-md text-left transition-colors duration-150"
          >
            <div className="min-w-0">
              <p className="text-ink-900 truncate text-[13px] font-semibold">{p.patient_name}</p>
              <p className="text-hint text-[11px]">{p.ward_or_opd || "—"} · {formatShortDateTime(p.created_at)}</p>
            </div>
            <Badge tone={PRESCRIPTION_STATUS_TONES[p.status]}>{PRESCRIPTION_STATUS_LABELS[p.status]}</Badge>
          </button>
        ))}
      </div>
    </Card>
  );
}
