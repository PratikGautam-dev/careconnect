"use client";

import { useState } from "react";
import { UserPlus } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { NewBookingDialog } from "@/components/portal/NewBookingDialog";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";

/** Status/config page for the Walk-in booking channel -- no new booking
 * flow here: this IS /portal/new-booking's existing staff-created-booking
 * dialog (source='staff' server-side, labeled "Walk-in" everywhere in the
 * UI), just given its own channel entry alongside WhatsApp/Website rather
 * than being reachable only from the Appointments page. */
export default function WalkInChannelPage() {
  const { hospital, ready } = usePortalGuard();
  const [bookingOpen, setBookingOpen] = useState(false);

  if (!hospital || !ready) return null;

  return (
    <PortalShell hospital={hospital} active="channels-walkin">
      <PageHeader
        title="Walk-in"
        description="Bookings staff create directly for a patient standing at the desk or calling in."
      />

      <Card className="p-space-5 max-w-2xl">
        <div className="gap-space-3 flex items-center">
          <div className="bg-brand-50 text-brand-700 flex h-11 w-11 shrink-0 items-center justify-center rounded-full">
            <UserPlus size={20} />
          </div>
          <div>
            <p className="text-ink-900 text-[14px] font-semibold">Walk-in booking</p>
            <Badge tone="brand">Always on</Badge>
          </div>
        </div>

        <p className="text-hint mt-space-5 text-[12.5px]">
          There&apos;s no separate walk-in flow to set up -- staff create these the same way they
          always have, through New Booking. Bookings created this way appear in Doctor
          Appointments, filtered by Channel = Walk-in.
        </p>

        <PermissionGate page="appointments" action="write">
          <Button
            variant="primary"
            className="mt-space-5"
            onClick={() => setBookingOpen(true)}
          >
            <UserPlus size={15} /> New walk-in booking
          </Button>
        </PermissionGate>
      </Card>

      <NewBookingDialog
        open={bookingOpen}
        onOpenChange={setBookingOpen}
        onBooked={() => setBookingOpen(false)}
      />
    </PortalShell>
  );
}
