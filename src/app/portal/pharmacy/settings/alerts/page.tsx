"use client";

import { useState } from "react";
import { ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePermission } from "@/lib/staffAuth";
import { usePharmacySettings } from "@/hooks/usePharmacySettings";

export default function PharmacyAlertsSettingsPage() {
  const { hospital, ready } = usePortalGuard();
  const canWrite = usePermission("pharmacy", "write");
  const { settings, updateSettings, saving } = usePharmacySettings(ready);

  const [nearExpiryDays, setNearExpiryDays] = useState("");
  const [alertsEnabled, setAlertsEnabled] = useState(true);
  const [loaded, setLoaded] = useState(false);
  if (settings && !loaded) {
    setLoaded(true);
    setNearExpiryDays(String(settings.near_expiry_days));
    setAlertsEnabled(settings.low_stock_alerts_enabled);
  }

  if (!hospital) return null;

  return (
    <PortalShell hospital={hospital} active="pharmacy-settings">
      <PageHeader
        title="Alerts & Thresholds"
        description="Set low-stock alerts, expiry thresholds, and other critical notifications."
        actions={<Button href="/portal/pharmacy/settings" variant="ghost"><ChevronLeft size={15} /> Back to Settings</Button>}
      />
      <Card className="max-w-xl p-space-5">
        <Field label="Near-Expiry Threshold (days)" hint="Batches expiring within this many days show up in the Near Expiry / Stock Alerts lists. Reorder level is still set per-medicine on the Medicine Master.">
          <Input type="number" min="1" value={nearExpiryDays} onChange={(e) => setNearExpiryDays(e.target.value)} />
        </Field>
        <label className="gap-space-2 mb-space-4 flex items-center text-[13px]">
          <input type="checkbox" checked={alertsEnabled} onChange={(e) => setAlertsEnabled(e.target.checked)} className="h-4 w-4" />
          Show low-stock alerts on the Pharmacy dashboard
        </label>
        {canWrite && (
          <Button
            disabled={saving}
            onClick={() => updateSettings({ near_expiry_days: Number(nearExpiryDays) || 30, low_stock_alerts_enabled: alertsEnabled })}
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        )}
      </Card>
    </PortalShell>
  );
}
