"use client";

import { ChevronDown, ChevronUp, Pencil, Plus, Search, Upload } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { DoctorScheduleForm } from "@/components/portal/DoctorScheduleForm";
import { DoctorLeaveManager } from "@/components/portal/DoctorLeaveManager";
import { DoctorSlotManager } from "@/components/portal/DoctorSlotManager";
import { DoctorTodayAppointments } from "@/components/portal/DoctorTodayAppointments";
import { DoctorCsvImport } from "@/components/portal/DoctorCsvImport";
import { useDoctors } from "@/hooks/useDoctors";

export default function PortalDoctorsPage() {
  const { hospital, ready } = usePortalGuard();
  // Backend route guards already 403 the actual mutations for clinic tenants
  // lacking manage_doctors -- this is just a UI convenience so those staff
  // don't hit an error after filling out a form. Fails open (keeps the
  // controls) while hospital hasn't loaded yet, matching PortalSidebar.
  const canManageDoctors = !hospital || hospital.admin_capabilities?.includes("manage_doctors");
  const {
    departments, doctors, error, load,
    newDeptName, setNewDeptName, addingDept, handleAddDepartment,
    showDoctorForm, showCsvImport, doctorForm, setDoctorForm, doctorErrors, savingDoctor,
    editingDoctorId, loadingDoctorForEdit,
    openAddDoctorForm, toggleCsvImport, cancelDoctorForm, handleSaveDoctor, handleEditDoctor, handleToggleActive,
    expandedId, setExpandedId, togglingId,
    searchQuery, setSearchQuery, activeFilter, setActiveFilter, filteredDoctors,
  } = useDoctors(ready);

  return (
    <PortalShell hospital={hospital} active="doctors">
        <div className="mb-space-5 flex flex-wrap items-center justify-between gap-space-3">
          <h1 className="text-display">Doctors &amp; departments</h1>
          {canManageDoctors && departments && departments.length > 0 && (
            <div className="flex gap-space-2">
              <Button variant="secondary" size="md" onClick={toggleCsvImport}>
                <Upload size={14} /> Bulk import
              </Button>
              <Button size="md" onClick={openAddDoctorForm}>
                <Plus size={14} /> Add doctor
              </Button>
            </div>
          )}
        </div>
        {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}
        {!canManageDoctors && (
          <p className="mb-space-4 text-[13px] text-ink-400">
            Doctor and department management isn&apos;t available for your account type. Contact support if you need
            changes made.
          </p>
        )}

        {!departments ? (
          <p className="text-[13px] text-ink-400">Loading…</p>
        ) : (
          <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-[1fr_320px]">
            <div className="space-y-space-4">
              {departments.length === 0 && (
                <Card className="p-space-4">
                  <p className="text-[12.5px] text-ink-400">Add a department first, then you can add doctors to it.</p>
                </Card>
              )}

              {showCsvImport && <DoctorCsvImport onImported={() => { load(); }} />}

              {showDoctorForm && (
                <>
                  <p className="text-label -mb-space-2 font-bold text-ink-900">
                    {editingDoctorId ? "Edit doctor" : "Add doctor"}
                  </p>
                  <DoctorScheduleForm
                    departments={departments}
                    value={doctorForm}
                    onChange={setDoctorForm}
                    onSave={handleSaveDoctor}
                    onCancel={cancelDoctorForm}
                    saving={savingDoctor}
                    errors={doctorErrors}
                  />
                </>
              )}

              <Card className="p-space-4">
                <h3 className="text-label mb-space-3 font-bold text-ink-900">Doctors</h3>
                {doctors.length > 0 && (
                  <div className="mb-space-3 flex flex-wrap gap-space-2">
                    <div className="relative min-w-[200px] flex-1">
                      <Search size={14} className="pointer-events-none absolute left-space-3 top-1/2 -translate-y-1/2 text-ink-400" />
                      <input
                        type="text"
                        placeholder="Search name or specialization…"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="h-10 w-full rounded-md border border-line bg-card pl-space-8 pr-space-3 text-[13px] text-ink-900 outline-none focus:border-brand-400"
                      />
                    </div>
                    <select
                      value={activeFilter}
                      onChange={(e) => setActiveFilter(e.target.value)}
                      className="h-10 rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-900"
                    >
                      <option value="all">All doctors</option>
                      <option value="active">Available only</option>
                      <option value="inactive">Unavailable only</option>
                    </select>
                  </div>
                )}
                {doctors.length === 0 ? (
                  <p className="py-space-4 text-center text-[13px] text-ink-400">No doctors yet.</p>
                ) : filteredDoctors.length === 0 ? (
                  <p className="py-space-4 text-center text-[13px] text-ink-400">No doctors match your search/filter.</p>
                ) : (
                  <ul className="divide-y divide-line">
                    {filteredDoctors.map((doc) => {
                      const expanded = expandedId === doc.id;
                      return (
                        <li key={doc.id} className="py-space-3">
                          <div className="flex items-center justify-between gap-space-3">
                            <div className="flex items-center gap-space-3">
                              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[13px] font-bold text-brand-700">
                                {doc.name.trim().charAt(0).toUpperCase() || "?"}
                              </div>
                              <div>
                                <p className="text-[13.5px] font-semibold text-ink-900">{doc.name}</p>
                                <p className="text-[12px] text-ink-600">
                                  {doc.department_name}
                                  {doc.specialization ? ` · ${doc.specialization}` : ""}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-space-3">
                              {canManageDoctors && (
                                <button
                                  type="button"
                                  onClick={() => handleEditDoctor(doc)}
                                  disabled={loadingDoctorForEdit === doc.id}
                                  className="text-ink-400 hover:text-ink-700 disabled:opacity-50"
                                  title="Edit doctor"
                                >
                                  <Pencil size={15} />
                                </button>
                              )}
                              <Badge tone={doc.is_active ? "success" : "neutral"}>
                                {doc.is_active ? "Available" : "Unavailable"}
                              </Badge>
                              <button
                                type="button"
                                onClick={() => handleToggleActive(doc)}
                                disabled={togglingId === doc.id || !canManageDoctors}
                                role="switch"
                                aria-checked={doc.is_active}
                                className={`relative h-6 w-11 shrink-0 rounded-full transition-colors duration-150 ${
                                  doc.is_active ? "bg-brand-600" : "bg-line"
                                } ${togglingId === doc.id ? "opacity-60" : ""}`}
                              >
                                <span
                                  className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-150 ${
                                    doc.is_active ? "translate-x-[22px]" : "translate-x-0.5"
                                  }`}
                                />
                              </button>
                              <button
                                type="button"
                                onClick={() => setExpandedId(expanded ? null : doc.id)}
                                className="text-ink-400 hover:text-ink-700"
                              >
                                {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                              </button>
                            </div>
                          </div>
                          {expanded && (
                            <div className="mt-space-3 space-y-space-3">
                              <DoctorTodayAppointments doctorId={doc.id} />
                              <DoctorSlotManager doctorId={doc.id} />
                              <DoctorLeaveManager doctorId={doc.id} />
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </Card>
            </div>

            <Card className="h-fit p-space-4">
              <h3 className="text-label mb-space-3 font-bold text-ink-900">Departments</h3>
              {canManageDoctors && (
                <form onSubmit={handleAddDepartment} className="mb-space-3 flex gap-space-2">
                  <Input placeholder="New department" value={newDeptName} onChange={(e) => setNewDeptName(e.target.value)} />
                  <Button type="submit" size="md" disabled={addingDept || !newDeptName.trim()}>
                    <Plus size={14} />
                  </Button>
                </form>
              )}
              {departments.length === 0 ? (
                <p className="text-[12.5px] text-ink-400">No departments yet.</p>
              ) : (
                <ul className="space-y-space-1">
                  {departments.map((d) => (
                    <li key={d.id} className="rounded-md bg-paper px-space-3 py-space-2 text-[13px] text-ink-900">
                      {d.name}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        )}
    </PortalShell>
  );
}
