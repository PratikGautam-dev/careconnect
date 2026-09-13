"use client";

import { HolidayApplicationView } from "@/components/portal/HolidayApplicationView";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePermission } from "@/lib/staffAuth";

export default function HolidayApplicationPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("holiday_application", "view");
  const canWrite = usePermission("holiday_application", "write");

  if (!ready) return null;

  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="holiday-application">
        <p className="text-[13px] text-ink-400">You don&apos;t have access to Holiday Application.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="holiday-application">
      <HolidayApplicationView canWrite={canWrite} />
    </PortalShell>
  );
}
