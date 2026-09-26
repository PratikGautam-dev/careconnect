"use client";

import { Building2, Calendar, ImageIcon, Link2, Mail, Tag } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { formatDate } from "@/lib/formatDate";
import type { SupportTicketRow, TicketStatus } from "@/hooks/useAdminSupportTickets";
import { PriorityLabel, StatusBadge } from "./support-ticket-columns";

const STATUS_OPTIONS: TicketStatus[] = ["open", "in_process", "on_hold", "completed"];
const STATUS_LABEL: Record<TicketStatus, string> = {
  open: "Open",
  in_process: "In Process",
  on_hold: "On Hold",
  completed: "Completed",
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
  ticket: SupportTicketRow | null;
  onStatusChange: (ticketId: number, status: TicketStatus) => void;
  updating: boolean;
};

/** Right-rail "selected ticket" review card -- every field here is real
 * (support_tickets, migration 20260926134810). This is the ONLY place a
 * ticket is worked at all: there's no equivalent panel on the portal side,
 * since a hospital's own admin never reviews these. */
export function SupportTicketDetailPanel({ ticket, onStatusChange, updating }: Props) {
  if (!ticket) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-ink-400 text-center text-[13px]">
          Select a ticket to review it.
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-space-4">
      <div className="mb-space-3">
        <p className="text-brand-600 text-[11.5px] font-bold tracking-wide">
          {ticket.ticket_number}
        </p>
        <p className="text-ink-900 text-[15px] font-bold">{ticket.subject}</p>
        <p className="text-ink-400 text-[12px]">{ticket.category_name || "Uncategorized"}</p>
      </div>

      <div className="space-y-space-2 border-line pt-space-3 border-t">
        <DetailRow icon={Building2} label="Hospital" value={ticket.hospital_name} />
        <DetailRow
          icon={Mail}
          label="Submitted By"
          value={ticket.submitted_by_name || ticket.submitted_by_email}
        />
        <DetailRow
          icon={Tag}
          label="Priority"
          value={<PriorityLabel priority={ticket.priority} />}
        />
        <DetailRow icon={Calendar} label="Submitted On" value={formatDate(ticket.created_at)} />
        {ticket.problem_reference && (
          <DetailRow icon={Link2} label="Reference" value={ticket.problem_reference} />
        )}
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-ink-400">Status</span>
          <StatusBadge status={ticket.status} />
        </div>
      </div>

      <div className="mt-space-3 border-line bg-paper p-space-3 rounded-md border">
        <p className="mb-space-1 text-ink-400 text-[11px] font-semibold">Question</p>
        <p className="text-ink-900 text-[13px] whitespace-pre-wrap">{ticket.question}</p>
      </div>

      {ticket.attachment_url && (
        <a
          href={ticket.attachment_url}
          target="_blank"
          rel="noreferrer"
          className="mt-space-2 border-line gap-space-2 text-brand-600 p-space-3 flex items-center rounded-md border text-[13px] font-semibold hover:underline"
        >
          <ImageIcon size={14} /> View attachment
        </a>
      )}

      {ticket.resolved_at && (
        <p className="text-hint mt-space-2">Resolved on {formatDate(ticket.resolved_at)}.</p>
      )}

      <div className="mt-space-4 border-line pt-space-3 border-t">
        <p className="mb-space-2 text-ink-400 text-[11px] font-semibold">Change Status</p>
        <div className="gap-space-1 flex flex-wrap">
          {STATUS_OPTIONS.map((status) => (
            <button
              key={status}
              type="button"
              disabled={updating || status === ticket.status}
              onClick={() => onStatusChange(ticket.id, status)}
              className={
                "px-space-3 py-space-1.5 rounded-md text-[12.5px] font-semibold transition-colors disabled:cursor-not-allowed " +
                (status === ticket.status
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
