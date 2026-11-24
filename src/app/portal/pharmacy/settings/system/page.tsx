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

export default function PharmacySystemSettingsPage() {
  const { hospital, ready } = usePortalGuard();
  const canWrite = usePermission("pharmacy", "write");
  const { settings, updateSettings, saving } = usePharmacySettings(ready);

  const [salePrefix, setSalePrefix] = useState("");
  const [rxPrefix, setRxPrefix] = useState("");
  const [srPrefix, setSrPrefix] = useState("");
  const [prPrefix, setPrPrefix] = useState("");
  const [adjPrefix, setAdjPrefix] = useState("");
  const [loaded, setLoaded] = useState(false);
  if (settings && !loaded) {
    setLoaded(true);
    setSalePrefix(settings.sale_number_prefix);
    setRxPrefix(settings.prescription_number_prefix);
    setSrPrefix(settings.sales_return_number_prefix);
    setPrPrefix(settings.purchase_return_number_prefix);
    setAdjPrefix(settings.adjustment_number_prefix);
  }

  if (!hospital) return null;

  return (
    <PortalShell hospital={hospital} active="pharmacy-settings">
      <PageHeader
        title="System Preferences"
        description="Set general pharmacy preferences, workflow options, numbering, and other system-level settings."
        actions={<Button href="/portal/pharmacy/settings" variant="ghost"><ChevronLeft size={15} /> Back to Settings</Button>}
      />
      <Card className="max-w-xl p-space-5">
        <p className="text-label mb-space-3">Document Numbering Prefixes</p>
        <div className="gap-space-3 grid grid-cols-2">
          <Field label="Sale / Invoice" hint='e.g. "PH"'><Input value={salePrefix} onChange={(e) => setSalePrefix(e.target.value)} /></Field>
          <Field label="Prescription" hint='e.g. "RX"'><Input value={rxPrefix} onChange={(e) => setRxPrefix(e.target.value)} /></Field>
          <Field label="Sales Return" hint='e.g. "SR"'><Input value={srPrefix} onChange={(e) => setSrPrefix(e.target.value)} /></Field>
          <Field label="Purchase Return" hint='e.g. "PR"'><Input value={prPrefix} onChange={(e) => setPrPrefix(e.target.value)} /></Field>
          <Field label="Stock Adjustment" hint='e.g. "ADJ"'><Input value={adjPrefix} onChange={(e) => setAdjPrefix(e.target.value)} /></Field>
        </div>
        {canWrite && (
          <Button
            disabled={saving}
            onClick={() => updateSettings({
              sale_number_prefix: salePrefix.trim() || "PH",
              prescription_number_prefix: rxPrefix.trim() || "RX",
              sales_return_number_prefix: srPrefix.trim() || "SR",
              purchase_return_number_prefix: prPrefix.trim() || "PR",
              adjustment_number_prefix: adjPrefix.trim() || "ADJ",
            })}
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        )}
      </Card>
    </PortalShell>
  );
}
