"use client";

import { useState } from "react";
import { Bell, Clock, Network, Settings as SettingsIcon } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { AttendanceSettingsTab } from "./_components/AttendanceSettingsTab";
import { DepartmentsTab } from "./_components/DepartmentsTab";
import { GeneralSettingsTab } from "./_components/GeneralSettingsTab";
import { NotificationsTab } from "./_components/NotificationsTab";
import { SettingsTabsNav, type SettingsTabDef, type SettingsTabKey } from "./_components/SettingsTabsNav";

const TABS: SettingsTabDef[] = [
  { key: "general", label: "General", icon: SettingsIcon },
  { key: "departments", label: "Departments", icon: Network },
  { key: "notifications", label: "Notifications", icon: Bell },
  { key: "attendance", label: "Attendance", icon: Clock },
];

const BUILT_TABS: SettingsTabKey[] = ["general", "departments", "notifications", "attendance"];

/** /portal/settings. "General" mixes real fields (Appointment Types,
 * Diagnostic Tests, Leave Policy, Lab Service Areas, Google Calendar, plus
 * the fields in GeneralSettingsTab.tsx) with a few frontend-mock-only
 * ones. "Departments" and "Notifications" are fully real -- see
 * DepartmentsTab.tsx/useDepartmentsAdmin and NotificationsTab.tsx.
 * BUILT_TABS matches TABS exactly; the "not designed yet" fallback stays
 * as a safety net for a future tab added to TABS without being wired up here. */
export default function PortalSettingsPage() {
  const { hospital, ready } = usePortalGuard();
  const [tab, setTab] = useState<SettingsTabKey>("general");

  return (
    <PortalShell hospital={hospital} active="settings">
      <PageHeader title="Settings" description="Manage your hospital settings and preferences" />

      {!ready ? null : (
        <>
          <SettingsTabsNav tabs={TABS} active={tab} onChange={setTab} />

          {tab === "general" && <GeneralSettingsTab hospital={hospital} />}
          {tab === "departments" && <DepartmentsTab />}
          {tab === "notifications" && <NotificationsTab />}
          {tab === "attendance" && <AttendanceSettingsTab />}
          {!BUILT_TABS.includes(tab) && (
            <Card className="p-space-6">
              <p className="text-center text-[13px] text-ink-400">
                This tab hasn&apos;t been designed yet -- share its reference screenshot to build it out.
              </p>
            </Card>
          )}
        </>
      )}
    </PortalShell>
  );
}
