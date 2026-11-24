"use client";

import { useState } from "react";
import { ChevronLeft, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePermission } from "@/lib/staffAuth";
import { usePharmacyUnits } from "@/hooks/usePharmacySettings";

const KINDS = [
  { value: "dosage_form", label: "Dosage Form" },
  { value: "unit", label: "Pack Unit" },
];

export default function PharmacyUnitsSettingsPage() {
  const { hospital, ready } = usePortalGuard();
  const canWrite = usePermission("pharmacy", "write");
  const { units, createUnit, creating, deleteUnit } = usePharmacyUnits(ready);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("unit");

  if (!hospital) return null;

  return (
    <PortalShell hospital={hospital} active="pharmacy-settings">
      <PageHeader
        title="Units & Dosage"
        description="Configure units, dosage forms, strengths, and pack sizes (e.g., mg, ml, strip, vial)."
        actions={<Button href="/portal/pharmacy/settings" variant="ghost"><ChevronLeft size={15} /> Back to Settings</Button>}
      />
      <Card className="max-w-xl p-space-5">
        {canWrite && (
          <div className="gap-space-2 mb-space-4 flex">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. mg, strip, vial…" className="flex-1" />
            <select value={kind} onChange={(e) => setKind(e.target.value)} className="border-line bg-card px-space-3 text-ink-900 h-10 rounded-md border text-[13.5px]">
              {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
            </select>
            <Button disabled={creating || !name.trim()} onClick={async () => { await createUnit(name.trim(), kind); setName(""); }}>
              <Plus size={14} /> Add
            </Button>
          </div>
        )}
        {units.length === 0 ? (
          <p className="text-hint py-space-4 text-center text-[13px]">No units yet.</p>
        ) : (
          <div className="space-y-space-2">
            {units.map((u) => (
              <div key={u.id} className="border-line p-space-2 flex items-center justify-between rounded-md border">
                <span className="text-ink-900 text-[13px] font-medium">
                  {u.name} <span className="text-hint ml-space-2 text-[11px]">{KINDS.find((k) => k.value === u.kind)?.label || u.kind}</span>
                </span>
                {canWrite && (
                  <button type="button" onClick={() => deleteUnit(u.id)} className="text-error">
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </PortalShell>
  );
}
