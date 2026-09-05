"use client";

import { DoctorScheduleView } from "@/components/portal/DoctorScheduleView";
import { DoctorShell } from "@/components/doctor/DoctorShell";
import { useDoctorGuard } from "@/components/doctor/useDoctorGuard";

export default function DoctorSchedulePage() {
  const { doctor, ready } = useDoctorGuard();

  if (!ready) return null;

  return (
    <DoctorShell doctor={doctor} active="schedule">
      <DoctorScheduleView />
    </DoctorShell>
  );
}
