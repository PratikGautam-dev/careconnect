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
        <p className="text-ink-400 text-[13px]">
          You don&apos;t have access to Holiday Application.
        </p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="holiday-application">
      <HolidayApplicationView canWrite={canWrite} />
    </PortalShell>
  );
}
