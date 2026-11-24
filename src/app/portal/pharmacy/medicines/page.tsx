"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePermission } from "@/lib/staffAuth";
import { useMedicines, type Medicine } from "@/hooks/usePharmacyMedicines";
import { usePharmacyInventory } from "@/hooks/usePharmacyInventory";
import { createMedicineColumns } from "./_components/medicines-columns";
import { MedicineFormDialog } from "./_components/MedicineFormDialog";

/** Medicines catalog -- reachable from the Inventory page/sidebar entry,
 * no standalone nav item of its own (see PortalSidebar.tsx's own comment). */
export default function MedicinesPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("pharmacy", "view");
  const canWrite = usePermission("pharmacy", "write");
  const { medicines, isLoading, createMedicine, creating, updateMedicine, updating, setActive } = useMedicines(ready);
  const { addStock } = usePharmacyInventory(ready);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingMedicine, setEditingMedicine] = useState<Medicine | null>(null);

  if (!hospital) return null;
  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="pharmacy-inventory">
        <p className="text-hint text-[13px]">You don&apos;t have access to this page.</p>
      </PortalShell>
    );
  }

  const columns = createMedicineColumns({
    onEdit: (m) => {
      setEditingMedicine(m);
      setDialogOpen(true);
    },
    onToggleActive: (m) => setActive(m.id, !m.is_active),
  });

  return (
    <PortalShell hospital={hospital} active="pharmacy-inventory">
      <PageHeader
        title="Medicines"
        description="The pharmacy's medicine catalog -- stock is managed from the Inventory page."
        actions={
          canWrite && (
            <Button
              onClick={() => {
                setEditingMedicine(null);
                setDialogOpen(true);
              }}
            >
              <Plus size={15} /> Add Medicine
            </Button>
          )
        }
      />
      <Card className="p-space-5">
        <DataTable
          columns={columns}
          data={medicines}
          getRowId={(m) => String(m.id)}
          loading={isLoading}
          emptyMessage="No medicines added yet."
          pageSizeOptions={[10, 25, 50]}
          tableId="pharmacy-medicines"
          enableColumnVisibility
        />
      </Card>

      <MedicineFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        medicine={editingMedicine}
        submitting={editingMedicine ? updating : creating}
        onSubmit={(form) => (editingMedicine ? updateMedicine(editingMedicine.id, form) : createMedicine(form))}
        onAddInitialStock={(medicineId, stock) =>
          addStock({
            medicine_id: String(medicineId),
            batch_number: stock.batch_number,
            expiry_date: stock.expiry_date,
            quantity: stock.quantity,
            cost_price: stock.cost_price,
            supplier_id: "",
          })
        }
      />
    </PortalShell>
  );
}
