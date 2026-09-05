"use client";

import { DoctorDashboardView } from "@/components/portal/DoctorDashboardView";
import { DoctorShell } from "@/components/doctor/DoctorShell";
import { useDoctorGuard } from "@/components/doctor/useDoctorGuard";

export default function DoctorDashboardPage() {
  const { doctor, ready } = useDoctorGuard();

  if (!ready) return null;

  return (
    <DoctorShell doctor={doctor} active="dashboard">
      <DoctorDashboardView />
    </DoctorShell>
  );
}
