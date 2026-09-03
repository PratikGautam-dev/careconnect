"use client";

import { Suspense } from "react";
import { GoogleCalendarCard } from "@/components/doctor/GoogleCalendarCard";
import { DoctorScheduleView } from "@/components/portal/DoctorScheduleView";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { getStaffSession, usePermission } from "@/lib/staffAuth";

function PortalSchedulePageContent() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("schedule", "view");
  const isDoctor = getStaffSession()?.role === "doctor";

  if (!ready) return null;

  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="schedule">
        <p className="text-[13px] text-ink-400">You don&apos;t have access to Schedule.</p>
      </PortalShell>
    );
  }

  // The underlying schedule/leave API is doctor-scoped (there's no "whose
  // schedule" concept for any other role) -- a hospital can toggle this page
  // visible for another role via Roles & Permissions, but only an account
  // whose role is actually "doctor" has a schedule of their own to show.
  if (!isDoctor) {
    return (
      <PortalShell hospital={hospital} active="schedule">
        <p className="text-[13px] text-ink-400">Your account isn&apos;t linked to a doctor profile, so there&apos;s no schedule to manage here.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="schedule">
      <DoctorScheduleView />
      <div className="mt-space-4">
        <GoogleCalendarCard />
      </div>
    </PortalShell>
  );
}

export default function PortalSchedulePage() {
  return (
    <Suspense>
      <PortalSchedulePageContent />
    </Suspense>
  );
}
