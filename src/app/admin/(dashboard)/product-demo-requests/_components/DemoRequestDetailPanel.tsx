"use client";

import { Building2, Calendar, Mail, Phone } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { formatDate } from "@/lib/formatDate";
import type { DemoRequestStatus, ProductDemoRequestRow } from "@/hooks/useAdminProductDemoRequests";
import { StatusBadge } from "./demo-request-columns";

const STATUS_OPTIONS: DemoRequestStatus[] = ["new", "contacted", "scheduled", "closed"];
const STATUS_LABEL: Record<DemoRequestStatus, string> = {
  new: "New",
  contacted: "Contacted",
  scheduled: "Scheduled",
  closed: "Closed",
};

function DetailRow({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Building2;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="gap-space-3 flex items-center justify-between text-[13px]">
      <span className="gap-space-2 text-ink-400 flex items-center">
        <Icon size={14} className="shrink-0" /> {label}
      </span>
      <span className="text-ink-900 truncate text-right font-medium">{value}</span>
    </div>
  );
}

type Props = {
  request: ProductDemoRequestRow | null;
  onStatusChange: (requestId: number, status: DemoRequestStatus) => void;
  updating: boolean;
};

/** Right-rail "selected lead" review card -- mirrors SupportTicketDetailPanel's
 * own layout. This is the only place a demo request is worked; there's no
 * hospital-side equivalent since the submitter never has a hospital yet. */
export function DemoRequestDetailPanel({ request, onStatusChange, updating }: Props) {
  if (!request) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-ink-400 text-center text-[13px]">
          Select a request to review it.
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-space-4">
      <div className="mb-space-3">
        <p className="text-brand-600 text-[11.5px] font-bold tracking-wide">
          {request.request_number}
        </p>
        <p className="text-ink-900 text-[15px] font-bold">{request.name}</p>
        <p className="text-ink-400 text-[12px]">{request.hospital_name || "No hospital given"}</p>
      </div>

      <div className="space-y-space-2 border-line pt-space-3 border-t">
        <DetailRow icon={Mail} label="Email" value={request.email} />
        {request.phone && <DetailRow icon={Phone} label="Phone" value={request.phone} />}
        {request.hospital_name && (
          <DetailRow icon={Building2} label="Hospital" value={request.hospital_name} />
        )}
        <DetailRow icon={Calendar} label="Submitted On" value={formatDate(request.created_at)} />
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-ink-400">Status</span>
          <StatusBadge status={request.status} />
        </div>
      </div>

      {request.message && (
        <div className="mt-space-3 border-line bg-paper p-space-3 rounded-md border">
          <p className="mb-space-1 text-ink-400 text-[11px] font-semibold">Message</p>
          <p className="text-ink-900 text-[13px] whitespace-pre-wrap">{request.message}</p>
        </div>
      )}

      <div className="mt-space-4 border-line pt-space-3 border-t">
        <p className="mb-space-2 text-ink-400 text-[11px] font-semibold">Change Status</p>
        <div className="gap-space-1 flex flex-wrap">
          {STATUS_OPTIONS.map((status) => (
            <button
              key={status}
              type="button"
              disabled={updating || status === request.status}
              onClick={() => onStatusChange(request.id, status)}
              className={
                "px-space-3 py-space-1.5 rounded-md text-[12.5px] font-semibold transition-colors disabled:cursor-not-allowed " +
                (status === request.status
                  ? "bg-brand-600 text-white"
                  : "text-ink-600 bg-black/4 hover:bg-black/8 disabled:opacity-50")
              }
            >
              {STATUS_LABEL[status]}
            </button>
          ))}
        </div>
      </div>
    </Card>
  );
}
