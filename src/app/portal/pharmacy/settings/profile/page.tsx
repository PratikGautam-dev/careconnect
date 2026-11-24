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

export default function PharmacyProfileSettingsPage() {
  const { hospital, ready } = usePortalGuard();
  const canWrite = usePermission("pharmacy", "write");
  const { settings, updateSettings, saving } = usePharmacySettings(ready);

  const [branchName, setBranchName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [hours, setHours] = useState("");
  const [loaded, setLoaded] = useState(false);

  if (settings && !loaded) {
    setLoaded(true);
    setBranchName(settings.profile_branch_name || "");
    setPhone(settings.profile_contact_phone || "");
    setEmail(settings.profile_contact_email || "");
    setHours(settings.profile_operating_hours || "");
  }

  if (!hospital) return null;

  return (
    <PortalShell hospital={hospital} active="pharmacy-settings">
      <PageHeader
        title="Pharmacy Profile"
        description="Manage pharmacy details, branch info, contact, and operational timings."
        actions={<Button href="/portal/pharmacy/settings" variant="ghost"><ChevronLeft size={15} /> Back to Settings</Button>}
      />
      <Card className="max-w-xl p-space-5">
        <Field label="Branch Name"><Input value={branchName} onChange={(e) => setBranchName(e.target.value)} /></Field>
        <Field label="Contact Phone"><Input value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
        <Field label="Contact Email"><Input value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Operating Hours" hint="e.g. 9:00 AM - 9:00 PM"><Input value={hours} onChange={(e) => setHours(e.target.value)} /></Field>
        {canWrite && (
          <Button
            disabled={saving}
            onClick={() => updateSettings({
              profile_branch_name: branchName.trim() || null,
              profile_contact_phone: phone.trim() || null,
              profile_contact_email: email.trim() || null,
              profile_operating_hours: hours.trim() || null,
            })}
          >
            {saving ? "Saving…" : "Save Profile"}
          </Button>
        )}
      </Card>
    </PortalShell>
  );
}
