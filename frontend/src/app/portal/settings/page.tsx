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

/** /portal/settings -- being rebuilt tab-by-tab to match a reference
 * mockup. "General" is mostly frontend-mock (a handful of fields wired to
 * real settings -- see GeneralSettingsTab.tsx's own doc comment, which now
 * also carries the real Appointment Types, Diagnostic Tests, Leave Policy,
 * Lab Service Areas, and Google Calendar sections moved over from the
 * legacy page); "Departments" is fully real (see DepartmentsTab.tsx /
 * useDepartmentsAdmin, and portal/routes/departments.py on the backend)
 * since the user explicitly asked for that one to be wired, not mocked;
 * "Notifications" is also real (see NotificationsTab.tsx) -- Notification
 * Preferences + message content (welcome/closing messages, reminders).
 * "Integrations" and "Security" were removed entirely (not just left
 * unbuilt) -- confirmed with the user, since neither had a reference or
 * any real content of its own (Google Calendar, briefly Integrations' only
 * occupant, now lives in General instead). All three of these tabs are
 * real and built, so BUILT_TABS below currently matches TABS exactly --
 * the "not designed yet" fallback stays only as a safety net for a future
 * tab added to TABS without also being wired up here. The former "Hospital
 * Profile" tab was deleted entirely too -- its real Hospital Name +
 * Contact Information fields moved into General, Bed Capacity moved to a
 * "Manage Beds" dialog on the Daycare Appointments page, and the rest was
 * frontend-mock-only with no real field to preserve. The previous fully
 * real, backend-wired settings page is preserved as-is at ../_reference/
 * legacy-general-settings-page.tsx purely for historical reference now
 * that every real section from it has a new home. */
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
