"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Bell,
  CalendarDays,
  Clock,
  CreditCard,
  Network,
  Settings as SettingsIcon,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { AppointmentsTab } from "./_components/AppointmentsTab";
import { AttendanceSettingsTab } from "./_components/AttendanceSettingsTab";
import { BillingTab } from "./_components/BillingTab";
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
  // { key: "procedures", label: "Procedures", icon: Stethoscope },
  { key: "notifications", label: "Notifications", icon: Bell },
  { key: "attendance", label: "Attendance", icon: Clock },
  { key: "plan", label: "Plan", icon: CreditCard },
];

const BUILT_TABS: SettingsTabKey[] = [
  "general",
  "appointments",
  "departments",
  // "procedures",
  "notifications",
  "attendance",
  "plan",
];

/** /portal/settings. "General" now covers Hospital Information, Contact
 * Information, Security & Session Settings, Leave Policy, and Google
 * Calendar (a mix of real fields and a few frontend-mock-only ones) --
 * Appointment Settings, Fees & Follow-up Window, Appointment Types,
 * Diagnostic Tests, and Lab Service Areas moved to their own "Appointments" tab (see
 * AppointmentsTab.tsx), since General had grown too many appointment-
 * related sections to stay legible. "Departments" and "Notifications" are
 * fully real -- see DepartmentsTab.tsx/useDepartmentsAdmin and
 * NotificationsTab.tsx. BUILT_TABS matches TABS exactly; the "not designed
 * yet" fallback stays as a safety net for a future tab added to TABS
 * without being wired up here. */
export default function PortalSettingsPage() {
  return (
    <Suspense fallback={null}>
      <PortalSettingsPageInner />
    </Suspense>
  );
}

function PortalSettingsPageInner() {
  const { hospital, ready } = usePortalGuard();
  // SubscriptionGate's "Go to plan" CTA links here with ?tab=plan so
  // a blocked hospital lands directly on the tab that can unblock it,
  // instead of General -- any other/missing value falls back to General.
  // useSearchParams() requires the Suspense boundary above (Next.js bails
  // out of static rendering otherwise).
  const searchParams = useSearchParams();
  const initialTab = BUILT_TABS.includes(searchParams.get("tab") as SettingsTabKey)
    ? (searchParams.get("tab") as SettingsTabKey)
    : "general";
  const [tab, setTab] = useState<SettingsTabKey>(initialTab);
  // !hospital means "still loading", not "no capabilities".
  // const canManageProcedures =
  //   !hospital || hospital.admin_capabilities?.includes("manage_procedures");
  // Clinics have no doctor/department management at all (portal/
  // capabilities.py's MANAGE_DEPARTMENTS, tenant-type-driven) -- same
  // "platform hasn't configured this module" reasoning AppointmentsTab.tsx
  // already applies to Diagnostic Tests/Lab Service Areas/Procedures, just
  // for the whole top-level Departments tab instead of a card within one.
  const canManageDepartments =
    !hospital || hospital.admin_capabilities?.includes("manage_departments");
  const visibleTabs = TABS.filter((t) => t.key !== "departments" || canManageDepartments);

  return (
    <PortalShell hospital={hospital} active="settings">
      <PageHeader title="Settings" description="Manage your hospital settings and preferences" />

      {!ready ? null : (
        <>
          <SettingsTabsNav tabs={visibleTabs} active={tab} onChange={setTab} />

          {tab === "general" && <GeneralSettingsTab hospital={hospital} />}
          {tab === "appointments" && <AppointmentsTab hospital={hospital} />}
          {tab === "departments" &&
            (canManageDepartments ? (
              <DepartmentsTab />
            ) : (
              <Card className="p-space-6">
                <p className="text-ink-400 text-center text-[13px]">
                  Departments aren&apos;t available for your account.
                </p>
              </Card>
            ))}
          {/* {tab === "procedures" && <ProceduresManager canManage={!!canManageProcedures} />} */}
          {tab === "notifications" && <NotificationsTab />}
          {tab === "attendance" && <AttendanceSettingsTab />}
          {tab === "plan" && <BillingTab />}
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
