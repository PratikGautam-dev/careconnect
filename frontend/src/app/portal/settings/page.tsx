"use client";

import { useState } from "react";
import { Bell, Building2, Network, Link2, Settings as SettingsIcon, ShieldCheck } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { DepartmentsTab } from "./_components/DepartmentsTab";
import { GeneralSettingsTab } from "./_components/GeneralSettingsTab";
import { HospitalProfileTab } from "./_components/HospitalProfileTab";
import { SettingsTabsNav, type SettingsTabDef, type SettingsTabKey } from "./_components/SettingsTabsNav";

const TABS: SettingsTabDef[] = [
  { key: "general", label: "General", icon: SettingsIcon },
  { key: "hospital-profile", label: "Hospital Profile", icon: Building2 },
  { key: "departments", label: "Departments", icon: Network },
  { key: "notifications", label: "Notifications", icon: Bell },
  { key: "integrations", label: "Integrations", icon: Link2 },
  { key: "security", label: "Security", icon: ShieldCheck },
];

const BUILT_TABS: SettingsTabKey[] = ["general", "hospital-profile", "departments"];

/** /portal/settings -- being rebuilt tab-by-tab to match a reference
 * mockup, one screenshot per tab. "General" and "Hospital Profile" are
 * mostly frontend-mock (a handful of fields wired to real settings -- see
 * each file's own doc comment); "Departments" is fully real (see
 * DepartmentsTab.tsx / useDepartmentsAdmin, and portal/routes/
 * departments.py on the backend) since the user explicitly asked for that
 * one to be wired, not mocked. The rest are placeholders until their own
 * reference arrives. The previous fully real, backend-wired settings page
 * (welcome message, reminders, appointment types, diagnostic tests, leave
 * policy, Google Calendar, lab service areas...) is preserved as-is at
 * _reference/legacy-general-settings-page.tsx so nothing gets lost while
 * that functionality finds a new home across these tabs. */
export default function PortalSettingsPage() {
  const { hospital, ready } = usePortalGuard();
  const [tab, setTab] = useState<SettingsTabKey>("general");

  return (
    <PortalShell hospital={hospital} active="settings">
      <PageHeader title="Settings" description="Manage your hospital settings and preferences" />

      {!ready ? null : (
        <>
          <SettingsTabsNav tabs={TABS} active={tab} onChange={setTab} />

          {tab === "general" && <GeneralSettingsTab />}
          {tab === "hospital-profile" && <HospitalProfileTab hospitalName={hospital?.name ?? ""} />}
          {tab === "departments" && <DepartmentsTab />}
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
