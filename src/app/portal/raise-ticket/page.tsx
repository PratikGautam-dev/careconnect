"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { NewSupportTicketDialog } from "@/components/portal/NewSupportTicketDialog";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePermission } from "@/lib/staffAuth";
import { useMySupportTickets } from "@/hooks/useSupportTickets";
import { myTicketColumns } from "./_components/my-ticket-columns";

/** Self-service ticket submission -- any role can open this (portal/
 * permissions.py's "raise_ticket" page key defaults to view+write for
 * every role). Lists this caller's own past tickets below (GET .../mine,
 * read-only -- reviewing/working a ticket stays the platform super admin's
 * own surface, admin/support_tickets_api.py), same table shape as that
 * page's own queue. */
export default function RaiseTicketPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("raise_ticket", "view");
  const canWrite = usePermission("raise_ticket", "write");
  const { tickets, error, load } = useMySupportTickets(ready && canView);
  const [dialogOpen, setDialogOpen] = useState(false);

  if (!ready) return null;

  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="raise-ticket">
        <p className="text-ink-400 text-[13px]">You don&apos;t have access to Support Tickets.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="raise-ticket">
      <PageHeader
        title="Raise a Ticket"
        description="Let our support team know about an issue with your account."
        actions={
          canWrite && (
            <Button type="button" onClick={() => setDialogOpen(true)}>
              <Plus size={14} /> Raise a ticket
            </Button>
          )
        }
      />

      <NewSupportTicketDialog open={dialogOpen} onOpenChange={setDialogOpen} onCreated={load} />

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      <Card className="p-space-4">
        <DataTable
          columns={myTicketColumns}
          data={tickets ?? []}
          getRowId={(t) => String(t.id)}
          loading={!tickets}
          pageSize={10}
          pageSizeOptions={[10, 25, 50]}
          emptyMessage="You haven't raised any tickets yet."
        />
      </Card>
    </PortalShell>
  );
}
