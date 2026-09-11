"use client";

import { useState } from "react";
import { Beaker, CalendarPlus, FlaskConical, Plus, UserPlus, FileDown } from "lucide-react";
import { NewBookingDialog } from "./NewBookingDialog";
import { NewTestBookingDialog } from "./NewTestBookingDialog";
import { QuickActions, type QuickAction } from "./QuickActions";

type Props = { className?: string };

// Add doctor/Add staff/Create test navigate to the existing management
// pages, which already own their add-forms (Create test = define a new
// bookable test TYPE, in Settings -- different from Book test below, which
// books an appointment against an EXISTING test). Book appointment/Book test
// open the same NewBookingDialog/NewTestBookingDialog the Doctor
// appointments/Diagnostic & lab pages' own "Add new appointment"/"New test
// booking" quick actions do, rather than just linking there. Export has no
// backend anywhere in this app -- disabled, same "Coming soon" convention
// PortalSidebar uses for its own unbuilt nav items.
export function DashboardQuickActions({ className }: Props) {
  const [bookingOpen, setBookingOpen] = useState(false);
  const [testBookingOpen, setTestBookingOpen] = useState(false);

  const actions: QuickAction[] = [
    { label: "Add doctor", icon: UserPlus, href: "/portal/doctors" },
    { label: "Add staff", icon: Plus, href: "/portal/settings/staff" },
    { label: "Book doctor appointment", icon: CalendarPlus, onClick: () => setBookingOpen(true) },
    { label: "Book diagnostic & lab appointment", icon: Beaker, onClick: () => setTestBookingOpen(true) },
    { label: "Create test", icon: FlaskConical, href: "/portal/settings" },
    { label: "Export report", icon: FileDown, disabled: true, title: "Coming soon" },
  ];

  return (
    <>
      <QuickActions actions={actions} cardClassName={className} />
      {/* onBooked is a no-op -- the dashboard's own usePortalDashboard hook
          already polls on an interval, so a new booking shows up shortly
          without needing a manual refetch hook threaded down here. */}
      <NewBookingDialog open={bookingOpen} onOpenChange={setBookingOpen} onBooked={() => {}} />
      <NewTestBookingDialog open={testBookingOpen} onOpenChange={setTestBookingOpen} onBooked={() => {}} />
    </>
  );
}
