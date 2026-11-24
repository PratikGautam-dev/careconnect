"use client";

import { ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePermission } from "@/lib/staffAuth";
import { usePharmacySettings } from "@/hooks/usePharmacySettings";

const INTEGRATIONS = [
  { key: "integration_emr_enabled" as const, label: "EMR", description: "Sync prescriptions and dispensing records with the hospital's EMR." },
  { key: "integration_billing_enabled" as const, label: "Billing", description: "Share pharmacy invoices with the main hospital Billing module." },
  { key: "integration_finance_enabled" as const, label: "Finance", description: "Export sales/purchase totals to the Finance module." },
];

/** Toggle-only -- this app has no real EMR/Billing/Finance system to
 * actually connect to yet, so these are persisted on/off switches staff can
 * set in advance, not live connections. */
export default function PharmacyIntegrationsSettingsPage() {
  const { hospital, ready } = usePortalGuard();
  const canWrite = usePermission("pharmacy", "write");
  const { settings, updateSettings, saving } = usePharmacySettings(ready);

  if (!hospital) return null;

  return (
    <PortalShell hospital={hospital} active="pharmacy-settings">
      <PageHeader
        title="Integrations"
        description="Configure integrations with EMR, Billing, Finance, and other hospital systems."
        actions={<Button href="/portal/pharmacy/settings" variant="ghost"><ChevronLeft size={15} /> Back to Settings</Button>}
      />
      <Card className="max-w-xl p-space-5">
        <div className="space-y-space-3">
          {INTEGRATIONS.map((i) => (
            <div key={i.key} className="border-line p-space-3 flex items-center justify-between rounded-md border">
              <div>
                <p className="text-ink-900 text-[13px] font-semibold">{i.label}</p>
                <p className="text-hint text-[11.5px]">{i.description}</p>
              </div>
              <button
                type="button"
                disabled={!canWrite || saving || !settings}
                onClick={() => settings && updateSettings({ [i.key]: !settings[i.key] })}
                className={`h-6 w-11 shrink-0 rounded-full transition-colors duration-150 ${settings?.[i.key] ? "bg-brand-600" : "bg-black/15"}`}
              >
                <span className={`block h-5 w-5 rounded-full bg-white transition-transform duration-150 ${settings?.[i.key] ? "translate-x-5" : "translate-x-0.5"}`} />
              </button>
            </div>
          ))}
        </div>
      </Card>
    </PortalShell>
  );
}
