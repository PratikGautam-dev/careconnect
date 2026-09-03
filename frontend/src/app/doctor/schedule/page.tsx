"use client";

import { Suspense } from "react";
import { DoctorScheduleView } from "@/components/portal/DoctorScheduleView";
import { DoctorShell } from "@/components/doctor/DoctorShell";
import { GoogleCalendarCard } from "@/components/doctor/GoogleCalendarCard";
import { useDoctorGuard } from "@/components/doctor/useDoctorGuard";

function DoctorSchedulePageContent() {
  const { doctor, ready } = useDoctorGuard();

  if (!ready) return null;

  return (
    <DoctorShell doctor={doctor} active="schedule">
      <DoctorScheduleView />
      <div className="mt-space-4">
        <GoogleCalendarCard />
      </div>
    </DoctorShell>
  );
}

export default function DoctorSchedulePage() {
  return (
    <Suspense>
      <DoctorSchedulePageContent />
    </Suspense>
  );
}
