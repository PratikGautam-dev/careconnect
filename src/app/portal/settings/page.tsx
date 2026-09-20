"use client";

import { useState } from "react";
import { Bell, CalendarDays, Clock, Network, Settings as SettingsIcon } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { AppointmentsTab } from "./_components/AppointmentsTab";
import { AttendanceSettingsTab } from "./_components/AttendanceSettingsTab";
import { DepartmentsTab } from "./_components/DepartmentsTab";
import { GeneralSettingsTab } from "./_components/GeneralSettingsTab";
import { NotificationsTab } from "./_components/NotificationsTab";
import {
  SettingsTabsNav,
  type SettingsTabDef,
  type SettingsTabKey,
} from "./_components/SettingsTabsNav";

const TABS: SettingsTabDef[] = [
  { key: "general", label: "General", icon: SettingsIcon },
  { key: "appointments", label: "Appointments", icon: CalendarDays },
  { key: "departments", label: "Departments", icon: Network },
  { key: "notifications", label: "Notifications", icon: Bell },
  { key: "attendance", label: "Attendance", icon: Clock },
];

const BUILT_TABS: SettingsTabKey[] = [
  "general",
  "appointments",
  "departments",
  "notifications",
  "attendance",
];

/** /portal/settings. "General" now covers Hospital Information, Contact
 * Information, Security & Session Settings, Leave Policy, and Google
 * Calendar (a mix of real fields and a few frontend-mock-only ones) --
 * Appointment Settings, Follow-up & Fees, Appointment Types, Diagnostic
 * Tests, and Lab Service Areas moved to their own "Appointments" tab (see
 * AppointmentsTab.tsx), since General had grown too many appointment-
 * related sections to stay legible. "Departments" and "Notifications" are
 * fully real -- see DepartmentsTab.tsx/useDepartmentsAdmin and
 * NotificationsTab.tsx. BUILT_TABS matches TABS exactly; the "not designed
 * yet" fallback stays as a safety net for a future tab added to TABS
 * without being wired up here. */
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
          {tab === "appointments" && <AppointmentsTab hospital={hospital} />}
          {tab === "departments" && <DepartmentsTab />}
          {tab === "notifications" && <NotificationsTab />}
          {tab === "attendance" && <AttendanceSettingsTab />}
          {!BUILT_TABS.includes(tab) && (
            <Card className="p-space-6">
              <p className="text-ink-400 text-center text-[13px]">
                This tab hasn&apos;t been designed yet -- share its reference screenshot to build it
                out.
              </p>
            </Card>
          )}
        </>
      )}
    </PortalShell>
  );
}
