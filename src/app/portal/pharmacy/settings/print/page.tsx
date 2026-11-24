"use client";

import { useState } from "react";
import { ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Textarea } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePermission } from "@/lib/staffAuth";
import { usePharmacySettings } from "@/hooks/usePharmacySettings";

const FORMATS = [
  { value: "A4", label: "A4" },
  { value: "thermal", label: "Thermal (80mm)" },
];

export default function PharmacyPrintSettingsPage() {
  const { hospital, ready } = usePortalGuard();
  const canWrite = usePermission("pharmacy", "write");
  const { settings, updateSettings, saving } = usePharmacySettings(ready);

  const [showLogo, setShowLogo] = useState(true);
  const [footerText, setFooterText] = useState("");
  const [format, setFormat] = useState("A4");
  const [loaded, setLoaded] = useState(false);
  if (settings && !loaded) {
    setLoaded(true);
    setShowLogo(settings.print_show_logo);
    setFooterText(settings.print_footer_text || "");
    setFormat(settings.print_format);
  }

  if (!hospital) return null;

  return (
    <PortalShell hospital={hospital} active="pharmacy-settings">
      <PageHeader
        title="Print Settings"
        description="Customize and manage print templates for bills, labels, and prescriptions."
        actions={<Button href="/portal/pharmacy/settings" variant="ghost"><ChevronLeft size={15} /> Back to Settings</Button>}
      />
      <Card className="max-w-xl p-space-5">
        <Field label="Print Format">
          <select value={format} onChange={(e) => setFormat(e.target.value)} className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px]">
            {FORMATS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </Field>
        <label className="gap-space-2 mb-space-4 flex items-center text-[13px]">
          <input type="checkbox" checked={showLogo} onChange={(e) => setShowLogo(e.target.checked)} className="h-4 w-4" />
          Show hospital logo on printed bills/labels
        </label>
        <Field label="Footer Text" hint="Optional">
          <Textarea value={footerText} onChange={(e) => setFooterText(e.target.value)} rows={3} />
        </Field>
        {canWrite && (
          <Button
            disabled={saving}
            onClick={() => updateSettings({ print_show_logo: showLogo, print_footer_text: footerText.trim() || null, print_format: format })}
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        )}
      </Card>
    </PortalShell>
  );
}
