"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Building2,
  CalendarX,
  Plus,
  Search,
  SlidersHorizontal,
  Upload,
  UserRound,
  UserRoundCheck,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { PortalShell } from "@/components/portal/PortalShell";
import { PortalTopBarActions } from "@/components/portal/PortalTopBarActions";
import { StatTile } from "@/components/portal/StatTile";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { DoctorScheduleForm } from "@/components/portal/DoctorScheduleForm";
import { DoctorCsvImport } from "@/components/portal/DoctorCsvImport";
import { AddStaffDialog } from "@/components/portal/AddStaffDialog";
import { NewLeaveRequestDialog } from "@/components/portal/NewLeaveRequestDialog";
import { RunningLateDialog } from "@/components/portal/RunningLateDialog";
import { ResetDoctorPasswordDialog } from "@/components/portal/ResetDoctorPasswordDialog";
import { StaffAttendanceHistoryDialog } from "@/components/portal/StaffAttendanceHistoryDialog";
import { StaffLeaveHistoryDialog } from "@/components/portal/StaffLeaveHistoryDialog";
import { usePermission } from "@/lib/staffAuth";
import { type Doctor, useDoctors } from "@/hooks/useDoctors";
import { createDoctorColumns } from "./_components/doctors-columns";
import { DoctorDetailPanel } from "./_components/DoctorDetailPanel";

export default function PortalDoctorsPage() {
  const { hospital, ready } = usePortalGuard();
  const [selectedDoctorId, setSelectedDoctorId] = useState<string | null>(null);
  const [createLoginFor, setCreateLoginFor] = useState<Doctor | null>(null);
  const [runningLateFor, setRunningLateFor] = useState<Doctor | null>(null);
  const [resetPasswordFor, setResetPasswordFor] = useState<Doctor | null>(null);
  const [leaveManagerFor, setLeaveManagerFor] = useState<Doctor | null>(null);
  const [attendanceHistoryStaffId, setAttendanceHistoryStaffId] = useState<number | null>(null);
  const [leaveHistoryStaffId, setLeaveHistoryStaffId] = useState<number | null>(null);
  const canViewAttendance = usePermission("attendance_overview", "view");
  const canViewLeaveHistory = usePermission("leave_requests", "view");
  const canManageLeave = usePermission("leave_requests", "write");
  // Backend route guards already 403 the actual mutations for clinic tenants
  // lacking manage_doctors -- this is just a UI convenience so those staff
  // don't hit an error after filling out a form. Fails open (keeps the
  // controls) while hospital hasn't loaded yet, matching PortalSidebar.
  const canManageDoctors = !hospital || hospital.admin_capabilities?.includes("manage_doctors");
  const {
    departments,
    doctors,
    onLeaveTodayCount,
    error,
    load,
    showDoctorForm,
    showCsvImport,
    doctorForm,
    setDoctorForm,
    doctorErrors,
    savingDoctor,
    editingDoctorId,
    loadingDoctorForEdit,
    openAddDoctorForm,
    toggleCsvImport,
    cancelDoctorForm,
    handleSaveDoctor,
    handleEditDoctor,
    handleToggleActive,
    togglingId,
    searchQuery,
    setSearchQuery,
    activeFilter,
    setActiveFilter,
    filteredDoctors,
  } = useDoctors(ready);

  const selectedDoctor: Doctor | null =
    doctors.find((d) => d.id === selectedDoctorId) || filteredDoctors[0] || null;
  const selectedIndex = selectedDoctor ? doctors.findIndex((d) => d.id === selectedDoctor.id) : 0;

  function selectDoctor(doc: Doctor) {
    setSelectedDoctorId(doc.id);
  }

  const columns = createDoctorColumns({
    onSelect: selectDoctor,
    canManage: canManageDoctors,
    togglingId,
    onToggleActive: handleToggleActive,
    loadingDoctorForEdit,
    onEdit: handleEditDoctor,
  });

  return (
    <PortalShell hospital={hospital} active="doctors">
      <PageHeader
        title="Doctors"
        description="Manage doctors, view profiles, availability and department information."
        actions={
          <>
            {canManageDoctors && (
              <>
                <Button variant="secondary" size="md" onClick={toggleCsvImport}>
                  <Upload size={14} /> Bulk import
                </Button>
                <Button size="md" onClick={openAddDoctorForm}>
                  <Plus size={14} /> Add doctor
                </Button>
              </>
            )}
            <PortalTopBarActions />
          </>
        }
      />

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}
      {!canManageDoctors && (
        <p className="mb-space-4 text-ink-400 text-[13px]">
          Doctor management isn&apos;t available for your account type. Contact support if you need
          changes made.
        </p>
      )}

      {!departments ? (
        <p className="text-ink-400 text-[13px]">Loading…</p>
      ) : (
        <>
          <div className="mb-space-4 gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="Total doctors"
              value={doctors.length}
              deltaPct={null}
              hint="Live count"
              icon={UserRound}
            />
            <StatTile
              label="Active doctors"
              value={doctors.filter((d) => d.is_active).length}
              deltaPct={null}
              hint={`of ${doctors.length} total`}
              icon={UserRoundCheck}
            />
            <StatTile
              label="On leave"
              value={onLeaveTodayCount}
              deltaPct={null}
              hint="Today"
              icon={CalendarX}
              tint="clay"
            />
            <StatTile
              label="Departments covered"
              value={departments.length}
              deltaPct={null}
              hint="Live count"
              icon={Building2}
            />
          </div>

          {departments.length === 0 && (
            <Card className="mb-space-4 p-space-4">
              <p className="text-ink-400 text-[12.5px]">
                No departments yet -- add one from{" "}
                <Link
                  href="/portal/settings"
                  className="text-brand-600 font-semibold hover:underline"
                >
                  Settings &rarr; Departments
                </Link>{" "}
                first, then you can add doctors to it.
              </p>
            </Card>
          )}

          {showCsvImport && (
            <div className="mb-space-4">
              <DoctorCsvImport
                onImported={() => {
                  load();
                }}
              />
            </div>
          )}

          <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
            <div className="lg:col-span-2">
              <Card className="p-space-4">
                <h3 className="text-label mb-space-3 text-ink-900 font-bold">All doctors</h3>
                {doctors.length > 0 && (
                  <div className="mb-space-3 gap-space-3 flex flex-wrap items-center">
                    <div className="relative min-w-[200px] flex-1">
                      <Search
                        size={14}
                        className="left-space-3 text-ink-400 pointer-events-none absolute top-1/2 -translate-y-1/2"
                      />
                      <input
                        type="text"
                        placeholder="Search doctors by name, department or specialization…"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="border-line bg-card pl-space-8 pr-space-3 text-ink-900 focus:border-brand-400 h-10 w-full rounded-md border text-[13px] outline-none"
                      />
                    </div>
                    <select
                      value={activeFilter}
                      onChange={(e) => setActiveFilter(e.target.value)}
                      className="border-line bg-card px-space-3 text-ink-900 h-10 rounded-md border text-[13px]"
                    >
                      <option value="all">All doctors</option>
                      <option value="active">Available only</option>
                      <option value="inactive">Unavailable only</option>
                    </select>
                    <Button type="button" variant="secondary" disabled title="Coming soon">
                      <SlidersHorizontal size={14} /> Filters
                    </Button>
                  </div>
                )}
                <DataTable
                  columns={columns}
                  data={filteredDoctors}
                  getRowId={(d) => d.id}
                  onRowClick={selectDoctor}
                  rowClassName={(d) => (d.id === selectedDoctor?.id ? "bg-brand-50" : "")}
                  emptyMessage={
                    doctors.length === 0
                      ? "No doctors yet."
                      : "No doctors match your search/filter."
                  }
                />
              </Card>
            </div>

            <div>
              <DoctorDetailPanel
                doctor={selectedDoctor}
                index={Math.max(selectedIndex, 0)}
                canManage={canManageDoctors}
                canViewAttendance={canViewAttendance}
                canViewLeaveHistory={canViewLeaveHistory}
                canManageLeave={canManageLeave}
                onEdit={handleEditDoctor}
                togglingId={togglingId}
                onToggleActive={handleToggleActive}
                onRunningLate={setRunningLateFor}
                onCreateLogin={setCreateLoginFor}
                onResetPassword={setResetPasswordFor}
                onManageLeave={setLeaveManagerFor}
                onViewAttendanceHistory={(d) => {
                  if (d.login_staff_id) setAttendanceHistoryStaffId(d.login_staff_id);
                }}
                onViewLeaveHistory={(d) => {
                  if (d.login_staff_id) setLeaveHistoryStaffId(d.login_staff_id);
                }}
              />
            </div>
          </div>
        </>
      )}

      <Dialog
        open={showDoctorForm}
        onOpenChange={(open) => {
          if (!open) cancelDoctorForm();
        }}
      >
        <DialogContent className="max-w-3xl">
          <DialogTitle>{editingDoctorId ? "Edit doctor" : "Add doctor"}</DialogTitle>
          {departments && (
            <DoctorScheduleForm
              departments={departments}
              value={doctorForm}
              onChange={setDoctorForm}
              onSave={handleSaveDoctor}
              onCancel={cancelDoctorForm}
              saving={savingDoctor}
              errors={doctorErrors}
            />
          )}
        </DialogContent>
      </Dialog>

      <AddStaffDialog
        open={createLoginFor !== null}
        onOpenChange={(open) => {
          if (!open) setCreateLoginFor(null);
        }}
        onCreated={load}
        presetDoctor={createLoginFor}
      />
      <RunningLateDialog
        doctor={runningLateFor}
        onOpenChange={(open) => {
          if (!open) setRunningLateFor(null);
        }}
      />
      <ResetDoctorPasswordDialog
        doctor={resetPasswordFor}
        onOpenChange={(open) => {
          if (!open) setResetPasswordFor(null);
        }}
      />
      <StaffAttendanceHistoryDialog
        staffId={attendanceHistoryStaffId}
        onOpenChange={(open) => {
          if (!open) setAttendanceHistoryStaffId(null);
        }}
      />
      <StaffLeaveHistoryDialog
        staffId={leaveHistoryStaffId}
        onOpenChange={(open) => {
          if (!open) setLeaveHistoryStaffId(null);
        }}
      />

      <NewLeaveRequestDialog
        open={leaveManagerFor !== null}
        onOpenChange={(open) => {
          if (!open) setLeaveManagerFor(null);
        }}
        subjectStaffId={leaveManagerFor?.login_staff_id ?? undefined}
        subjectName={leaveManagerFor?.name}
        onCreated={load}
      />
    </PortalShell>
  );
}
