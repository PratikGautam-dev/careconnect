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
import { usePharmacyCategories } from "@/hooks/usePharmacySettings";

export default function PharmacyCategoriesSettingsPage() {
  const { hospital, ready } = usePortalGuard();
  const canWrite = usePermission("pharmacy", "write");
  const { categories, createCategory, creating, deleteCategory } = usePharmacyCategories(ready);
  const [name, setName] = useState("");

  if (!hospital) return null;

  return (
    <PortalShell hospital={hospital} active="pharmacy-settings">
      <PageHeader
        title="Categories"
        description="Create and manage medicine categories (e.g., Tablets, Capsules, Injections, etc.)."
        actions={<Button href="/portal/pharmacy/settings" variant="ghost"><ChevronLeft size={15} /> Back to Settings</Button>}
      />
      <Card className="max-w-xl p-space-5">
        {canWrite && (
          <div className="gap-space-2 mb-space-4 flex">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="New category name…" className="flex-1" />
            <Button
              disabled={creating || !name.trim()}
              onClick={async () => { await createCategory(name.trim()); setName(""); }}
            >
              <Plus size={14} /> Add
            </Button>
          </div>
        )}
        {categories.length === 0 ? (
          <p className="text-hint py-space-4 text-center text-[13px]">No categories yet.</p>
        ) : (
          <div className="space-y-space-2">
            {categories.map((c) => (
              <div key={c.id} className="border-line p-space-2 flex items-center justify-between rounded-md border">
                <span className="text-ink-900 text-[13px] font-medium">{c.name}</span>
                {canWrite && (
                  <button type="button" onClick={() => deleteCategory(c.id)} className="text-error">
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
