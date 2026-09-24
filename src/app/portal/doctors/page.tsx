"use client";

import { useMemo, useState } from "react";
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
import { StatTile } from "@/components/portal/StatTile";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import {
  DoctorScheduleForm,
  emptyDoctorScheduleForm,
  type DoctorScheduleFormState,
} from "@/components/portal/DoctorScheduleForm";
import { DoctorCsvImport } from "@/components/portal/DoctorCsvImport";
import { AddStaffDialog } from "@/components/portal/AddStaffDialog";
import { NewLeaveRequestDialog } from "@/components/portal/NewLeaveRequestDialog";
import { RunningLateDialog } from "@/components/portal/RunningLateDialog";
import { ResetDoctorPasswordDialog } from "@/components/portal/ResetDoctorPasswordDialog";
import { StaffAttendanceHistoryDialog } from "@/components/portal/StaffAttendanceHistoryDialog";
import { StaffLeaveHistoryDialog } from "@/components/portal/StaffLeaveHistoryDialog";
import { usePermission } from "@/lib/staffAuth";
import { isPortalMutationError } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";
import {
  type Doctor,
  type DoctorPayload,
  useCreateDoctor,
  useDoctor,
  useDoctors,
  useToggleDoctorActive,
  useUpdateDoctor,
} from "@/hooks/useDoctors";
import { createDoctorColumns } from "./_components/doctors-columns";
import { DoctorDetailPanel } from "./_components/DoctorDetailPanel";

export default function PortalDoctorsPage() {
  const { hospital, ready } = usePortalGuard();
  const { departments, doctors, onLeaveTodayCount, error, load } = useDoctors(ready);
  const { fetchDoctor } = useDoctor();
  const createDoctor = useCreateDoctor();
  const updateDoctor = useUpdateDoctor();
  const toggleDoctorActive = useToggleDoctorActive();

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

  const [showDoctorForm, setShowDoctorForm] = useState(false);
  const [showCsvImport, setShowCsvImport] = useState(false);
  const [doctorForm, setDoctorForm] = useState<DoctorScheduleFormState>(emptyDoctorScheduleForm());
  const [doctorErrors, setDoctorErrors] = useState<string[]>([]);
  // Reuses the same DoctorScheduleForm the "Add doctor" flow uses --
  // editingDoctorId non-null is what distinguishes "save" meaning POST
  // /api/portal/doctors (create) vs POST /api/portal/doctors/{id} (update).
  const [editingDoctorId, setEditingDoctorId] = useState<string | null>(null);

  const [togglingId, setTogglingId] = useState<string | null>(null);

  // Search (name/specialization) + active/inactive filter, computed
  // client-side -- a hospital's own doctor list is small enough that a
  // server round trip per keystroke isn't needed.
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState("all");

  const filteredDoctors = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return doctors.filter((d) => {
      if (activeFilter === "active" && !d.is_active) return false;
      if (activeFilter === "inactive" && d.is_active) return false;
      if (!q) return true;
      return d.name.toLowerCase().includes(q) || (d.specialization || "").toLowerCase().includes(q);
    });
  }, [doctors, searchQuery, activeFilter]);

  const selectedDoctor: Doctor | null =
    doctors.find((d) => d.id === selectedDoctorId) || filteredDoctors[0] || null;
  const selectedIndex = selectedDoctor ? doctors.findIndex((d) => d.id === selectedDoctor.id) : 0;

  function selectDoctor(doc: Doctor) {
    setSelectedDoctorId(doc.id);
  }

  function openAddDoctorForm() {
    setShowDoctorForm(true);
    setShowCsvImport(false);
    setDoctorForm(emptyDoctorScheduleForm());
    setDoctorErrors([]);
    setEditingDoctorId(null);
  }

  function toggleCsvImport() {
    setShowCsvImport((v) => !v);
    setShowDoctorForm(false);
  }

  function closeCsvImport() {
    setShowCsvImport(false);
  }

  function cancelDoctorForm() {
    setShowDoctorForm(false);
    setEditingDoctorId(null);
  }

  async function handleSaveDoctor() {
    const working_hours = doctorForm.shifts
      .filter((s) => s.start && s.end)
      .map((s) => `${s.start}-${s.end}`);
    // Same "at least one working day and one complete shift" rule
    // admin/validation.py's own doctor-field validator enforces server-side
    // -- caught here first so the admin sees it immediately instead of
    // after a round-trip.
    if (doctorForm.working_days.length === 0) {
      setDoctorErrors(["Choose at least one working day."]);
      return;
    }
    if (working_hours.length === 0) {
      setDoctorErrors(["Add at least one shift with both a start and end time."]);
      return;
    }
    setDoctorErrors([]);
    const breaks = doctorForm.breaks
      .filter((b) => b && b.start && b.end)
      .map((b) => `${b.start}-${b.end}`);
    const payload: DoctorPayload = {
      department_id: doctorForm.department_id,
      name: doctorForm.name,
      specialization: doctorForm.specialization,
      qualification: doctorForm.qualification,
      years_experience: doctorForm.years_experience,
      working_days: doctorForm.working_days,
      working_hours,
      slot_duration_minutes: doctorForm.slot_duration_minutes,
      breaks,
      max_bookings_per_slot: doctorForm.max_bookings_per_slot,
      daily_booking_limit: doctorForm.daily_booking_limit,
      online_quota: doctorForm.online_quota,
      walkin_quota: doctorForm.walkin_quota,
      followup_duration_minutes: doctorForm.followup_duration_minutes,
      effective_from: doctorForm.effective_from,
      phone: doctorForm.phone,
      location: doctorForm.location,
    };

    try {
      const data = editingDoctorId
        ? await updateDoctor.mutateAsync({ doctorId: editingDoctorId, payload })
        : await createDoctor.mutateAsync(payload);
      if (data.errors?.length) {
        setDoctorErrors(data.errors);
        toast.error(editingDoctorId ? "Couldn't update doctor" : "Couldn't add doctor", data.errors[0]);
        return;
      }
      toast.success(editingDoctorId ? "Doctor updated" : "Doctor added");
      setDoctorForm(emptyDoctorScheduleForm());
      setShowDoctorForm(false);
      setEditingDoctorId(null);
      load();
    } catch (err) {
      if (isPortalMutationError(err)) {
        setDoctorErrors([err.message]);
        toast.error(editingDoctorId ? "Couldn't update doctor" : "Couldn't add doctor", err.message);
      }
    }
  }

  // Fetches the full record (working days/hours/breaks/quotas --
  // get_all_doctors_for_hospital()'s list-page shape above doesn't carry
  // these) and maps it into the same form shape "Add doctor" uses,
  // splitting each stored "HH:MM-HH:MM" string back into a shift/break row.
  async function handleEditDoctor(doc: Doctor) {
    let full: Record<string, unknown>;
    try {
      full = await fetchDoctor(doc.id);
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't load doctor", err.message);
      return;
    }
    const toRange = (s: string) => {
      const [start, end] = s.split("-");
      return { start: start || "", end: end || "" };
    };
    const shifts = ((full.working_hours as string[]) || []).map(toRange);
    setDoctorForm({
      department_id: (full.department_id as string) || "",
      name: (full.name as string) || "",
      specialization: (full.specialization as string) || "",
      qualification: (full.qualification as string) || "",
      years_experience: full.years_experience != null ? String(full.years_experience) : "",
      working_days: (full.working_days as string[]) || [],
      shifts: shifts.length > 0 ? shifts : [{ start: "", end: "" }],
      breaks: ((full.breaks as string[]) || []).map(toRange),
      slot_duration_minutes:
        full.slot_duration_minutes != null ? String(full.slot_duration_minutes) : "",
      max_bookings_per_slot:
        full.max_bookings_per_slot != null ? String(full.max_bookings_per_slot) : "1",
      daily_booking_limit: full.daily_booking_limit != null ? String(full.daily_booking_limit) : "",
      online_quota: full.online_quota != null ? String(full.online_quota) : "",
      walkin_quota: full.walkin_quota != null ? String(full.walkin_quota) : "",
      followup_duration_minutes:
        full.followup_duration_minutes != null ? String(full.followup_duration_minutes) : "",
      effective_from: (full.effective_from as string) || "",
      phone: (full.phone as string) || "",
      location: (full.location as string) || "",
    });
    setEditingDoctorId(doc.id);
    setDoctorErrors([]);
    setShowCsvImport(false);
    setShowDoctorForm(true);
  }

  async function handleToggleActive(doc: Doctor) {
    setTogglingId(doc.id);
    try {
      await toggleDoctorActive.mutateAsync({ doctorId: doc.id, isActive: !doc.is_active });
      toast.success(`${doc.name} marked ${doc.is_active ? "unavailable" : "available"}`);
      load();
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't update availability", err.message);
    } finally {
      setTogglingId(null);
    }
  }

  const columns = createDoctorColumns({
    onSelect: selectDoctor,
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
              saving={createDoctor.isPending || updateDoctor.isPending}
              errors={doctorErrors}
            />
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={showCsvImport}
        onOpenChange={(open) => {
          if (!open) closeCsvImport();
        }}
      >
        <DialogContent className="max-w-3xl">
          <DialogTitle>Bulk import from CSV</DialogTitle>
          <DoctorCsvImport
            onImported={() => {
              load();
              closeCsvImport();
            }}
          />
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
