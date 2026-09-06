"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { DiagnosticResourcesManager } from "@/components/portal/DiagnosticResourcesManager";
import { DiagnosticTestsManager } from "@/components/portal/DiagnosticTestsManager";

export default function PortalDiagnosticTestsPage() {
  const { hospital } = usePortalGuard();
  // Backend route guards already 403 the actual mutations -- this is just a
  // UI convenience, same fail-open-while-loading convention as doctors/page.tsx.
  const canManageTests = !hospital || hospital.admin_capabilities?.includes("manage_appointment_types");
  const canManageResources = !hospital || hospital.admin_capabilities?.includes("manage_diagnostic_resources");

  return (
    <PortalShell hospital={hospital} active="diagnostic_tests">
      <PageHeader
        title="Diagnostic tests"
        description="Manage the tests patients can book under Diagnostic Test / Lab Test, and the machines/equipment their date and time options are drawn from."
      />

      <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-[1fr_1fr]">
        <DiagnosticTestsManager canManage={!!canManageTests} />
        <DiagnosticResourcesManager canManage={!!canManageResources} />
      </div>
    </PortalShell>
  );
}
