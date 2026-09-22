"use client";

import { useMemo, useState } from "react";
import { CheckCircle2, Plus, Search, Stethoscope } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { StatTile } from "@/components/portal/StatTile";
import { useDepartments } from "@/hooks/useDepartments";
import {
  PROCEDURE_CATEGORIES,
  useProceduresAdmin,
  type Procedure,
  type ProcedureFields,
} from "@/hooks/useProcedures";
import type { PortalHospital } from "@/lib/portalAuth";
import { createProcedureColumns } from "./procedure-columns";
import { ProcedureFormDialog } from "./ProcedureFormDialog";

const STATUS_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive" },
];

const CATEGORY_OPTIONS = PROCEDURE_CATEGORIES.map((c) => ({ value: c.value, label: c.label }));

/** Settings -> Procedures tab -- the first admin UI over the daycare/
 * procedure catalog (name, category, price range). Modeled directly on
 * DepartmentsTab.tsx's list + add/edit dialog pattern: backend CRUD
 * (portal/routes/procedures.py) already existed, nothing in the frontend
 * called it before this tab. Gated by the same manage_procedures
 * admin_capabilities check AppointmentsTab.tsx already uses for Diagnostic
 * Tests/Lab Service Areas -- `!hospital` means "still loading", not "no
 * capabilities". */
export function ProceduresTab({ hospital }: { hospital: PortalHospital | null }) {
  const canManage = !hospital || hospital.admin_capabilities?.includes("manage_procedures");

  const { procedures, error, createProcedure, updateProcedure, setProcedureActive } =
    useProceduresAdmin(true);
  const departments = useDepartments(true) ?? [];

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");

  const [formOpen, setFormOpen] = useState(false);
  const [formProcedure, setFormProcedure] = useState<Procedure | null>(null);
  const [savingForm, setSavingForm] = useState(false);

  const filtered = useMemo(() => {
    if (!procedures) return [];
    const q = searchQuery.trim().toLowerCase();
    return procedures.filter((p) => {
      if (statusFilter === "active" && !p.is_active) return false;
      if (statusFilter === "inactive" && p.is_active) return false;
      if (categoryFilter !== "all" && p.category !== categoryFilter) return false;
      if (!q) return true;
      return p.name.toLowerCase().includes(q);
    });
  }, [procedures, searchQuery, statusFilter, categoryFilter]);

  const totalProcedures = procedures?.length ?? 0;
  const activeProcedures = procedures?.filter((p) => p.is_active).length ?? 0;

  function openAddDialog() {
    setFormProcedure(null);
    setFormOpen(true);
  }

  function openEditDialog(procedure: Procedure) {
    setFormProcedure(procedure);
    setFormOpen(true);
  }

  async function handleFormSubmit(fields: ProcedureFields) {
    setSavingForm(true);
    const ok = formProcedure
      ? await updateProcedure(formProcedure.id, fields)
      : await createProcedure(fields);
    setSavingForm(false);
    if (ok) setFormOpen(false);
  }

  async function handleToggleActive(procedure: Procedure) {
    await setProcedureActive(procedure.id, !procedure.is_active);
  }

  if (error) {
    return (
      <Card className="p-space-6">
        <p className="text-error text-center text-[13px]">{error}</p>
      </Card>
    );
  }

  return (
    <div className="gap-space-4 flex flex-col">
      <div className="gap-space-4 grid grid-cols-1 sm:grid-cols-2">
        <StatTile
          label="Total Procedures"
          value={totalProcedures}
          deltaPct={null}
          hint="Live count"
          icon={Stethoscope}
          tint="brand"
        />
        <StatTile
          label="Active Procedures"
          value={activeProcedures}
          deltaPct={null}
          hint={
            totalProcedures
              ? `${Math.round((activeProcedures / totalProcedures) * 100)}% of total`
              : "—"
          }
          icon={CheckCircle2}
          tint="success"
        />
      </div>

      <Card className="p-space-4">
        <div className="mb-space-3 gap-space-3 flex flex-wrap items-start justify-between">
          <div>
            <h3 className="text-label text-ink-900 font-bold">Procedure Catalog</h3>
            <p className="text-hint mt-space-1">
              Daycare/procedure types patients can book, with their estimated price range
            </p>
          </div>
          {canManage && (
            <Button size="md" onClick={openAddDialog}>
              <Plus size={14} /> New Procedure
            </Button>
          )}
        </div>

        <div className="mb-space-3 gap-space-3 flex flex-wrap items-center">
          <div className="relative min-w-50 flex-1">
            <Search
              size={14}
              className="left-space-3 text-ink-400 pointer-events-none absolute top-1/2 -translate-y-1/2"
            />
            <input
              type="text"
              placeholder="Search procedures…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="border-line bg-card pl-space-8 pr-space-3 text-ink-900 focus:border-brand-400 h-10 w-full rounded-md border text-[13px] outline-none"
            />
          </div>
          <FilterSelect
            value={categoryFilter}
            onChange={setCategoryFilter}
            allLabel="All Categories"
            options={CATEGORY_OPTIONS}
          />
          <FilterSelect
            value={statusFilter}
            onChange={setStatusFilter}
            allLabel="All Status"
            options={STATUS_OPTIONS}
          />
        </div>

        <DataTable
          columns={createProcedureColumns({
            onEdit: openEditDialog,
            onToggleActive: handleToggleActive,
          })}
          data={filtered}
          getRowId={(p) => String(p.id)}
          pageSize={10}
          pageSizeOptions={[10, 25, 50]}
          loading={!procedures}
          emptyMessage={
            procedures && procedures.length > 0
              ? "No procedures match your search/filters."
              : "No procedures yet."
          }
        />
      </Card>

      <ProcedureFormDialog
        open={formOpen}
        procedure={formProcedure}
        departments={departments}
        saving={savingForm}
        onClose={() => setFormOpen(false)}
        onSubmit={handleFormSubmit}
      />
    </div>
  );
}
