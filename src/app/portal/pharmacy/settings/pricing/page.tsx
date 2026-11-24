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

export default function PharmacyPricingSettingsPage() {
  const { hospital, ready } = usePortalGuard();
  const canWrite = usePermission("pharmacy", "write");
  const { settings, updateSettings, saving } = usePharmacySettings(ready);

  const [taxPercent, setTaxPercent] = useState("");
  const [loaded, setLoaded] = useState(false);
  if (settings && !loaded) {
    setLoaded(true);
    setTaxPercent(String(settings.default_tax_percent));
  }

  if (!hospital) return null;

  return (
    <PortalShell hospital={hospital} active="pharmacy-settings">
      <PageHeader
        title="Pricing & Taxes"
        description="Manage sale price, discounts, and tax rates (GST) applied to pharmacy sales."
        actions={<Button href="/portal/pharmacy/settings" variant="ghost"><ChevronLeft size={15} /> Back to Settings</Button>}
      />
      <Card className="max-w-xl p-space-5">
        <Field label="Default Tax Rate (GST %)" hint="Applied to every new prescription dispense and OTC/IPD sale going forward -- existing sales are unaffected.">
          <Input type="number" min="0" max="100" step="0.01" value={taxPercent} onChange={(e) => setTaxPercent(e.target.value)} />
        </Field>
        {canWrite && (
          <Button disabled={saving} onClick={() => updateSettings({ default_tax_percent: Number(taxPercent) || 0 })}>
            {saving ? "Saving…" : "Save"}
          </Button>
        )}
      </Card>
    </PortalShell>
  );
}
