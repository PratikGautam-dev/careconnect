"use client";

import { useMemo, useState } from "react";
import { Building2, CalendarX, Plus, Search, UserCheck, Users } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { PageHeader } from "@/components/ui/PageHeader";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { AddStaffDialog } from "@/components/portal/AddStaffDialog";
import { EditStaffDialog } from "@/components/portal/EditStaffDialog";
import { NewLeaveRequestDialog } from "@/components/portal/NewLeaveRequestDialog";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { PortalShell } from "@/components/portal/PortalShell";
import { StaffAttendanceHistoryDialog } from "@/components/portal/StaffAttendanceHistoryDialog";
import { StaffLeaveHistoryDialog } from "@/components/portal/StaffLeaveHistoryDialog";
import { StatTile } from "@/components/portal/StatTile";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePermission } from "@/lib/staffAuth";
import { formatHeaderDate } from "@/lib/formatDate";
import { useAttendanceOverview } from "@/hooks/useAttendanceOverview";
import { useDepartments } from "@/hooks/useDepartments";
import { useResetStaffPassword, useStaff, useToggleStaffActive } from "@/hooks/useStaff";
import { isPortalMutationError } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";
import { createStaffColumns, type StaffRow } from "./_components/staff-columns";
import { StaffDetailPanel } from "./_components/StaffDetailPanel";

const STATUS_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive" },
];

export default function StaffManagementPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("staff", "view");
  const canManage = usePermission("staff", "write");
  const canViewAttendance = usePermission("attendance_overview", "view");
  const canViewLeaveHistory = usePermission("leave_requests", "view");
  const canManageLeave = usePermission("leave_requests", "write");
  const departments = useDepartments(ready && canView);
  const { records: attendanceToday } = useAttendanceOverview(ready && canViewAttendance);

  const { staff, error, load } = useStaff(canView);
  const toggleStaffActive = useToggleStaffActive();
  const resetStaffPassword = useResetStaffPassword();

  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [resetPasswordTarget, setResetPasswordTarget] = useState<StaffRow | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [resetErrors, setResetErrors] = useState<string[]>([]);

  async function handleToggleActive(member: StaffRow) {
    setTogglingId(member.id);
    try {
      await toggleStaffActive.mutateAsync({ staffId: member.id, isActive: !member.is_active });
      toast.success(member.is_active ? "Staff member deactivated" : "Staff member activated");
      load();
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't update staff member", err.message);
    } finally {
      setTogglingId(null);
    }
  }

  function openResetPassword(member: StaffRow) {
    setResetPasswordTarget(member);
    setNewPassword("");
    setConfirmPassword("");
    setResetErrors([]);
  }

  function closeResetPassword() {
    setResetPasswordTarget(null);
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    if (!resetPasswordTarget) return;
    setResetErrors([]);
    try {
      await resetStaffPassword.mutateAsync({
        staffId: resetPasswordTarget.id,
        newPassword,
        confirmPassword,
      });
      toast.success(`Password reset for ${resetPasswordTarget.name}`);
      setResetPasswordTarget(null);
    } catch (err) {
      if (isPortalMutationError(err)) {
        setResetErrors([err.message]);
        toast.error("Couldn't reset password", err.message);
      }
    }
  }

  const [addStaffOpen, setAddStaffOpen] = useState(false);
  const [editingStaff, setEditingStaff] = useState<StaffRow | null>(null);
  const [attendanceHistoryStaffId, setAttendanceHistoryStaffId] = useState<number | null>(null);
  const [leaveHistoryStaffId, setLeaveHistoryStaffId] = useState<number | null>(null);
  const [manageLeaveFor, setManageLeaveFor] = useState<StaffRow | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const today = new Date();

  const rows: StaffRow[] = useMemo(() => staff || [], [staff]);
  const departmentOptions = useMemo(
    () => (departments || []).map((d) => ({ value: d.id, label: d.name })),
    [departments],
  );

  const filteredRows = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return rows.filter((s) => {
      if (departmentFilter !== "all" && s.department_id !== departmentFilter) return false;
      if (statusFilter !== "all" && (statusFilter === "active") !== s.is_active) return false;
      if (!q) return true;
      return (
        s.name.toLowerCase().includes(q) ||
        s.email.toLowerCase().includes(q) ||
        (s.department_name || "").toLowerCase().includes(q) ||
        (s.phone || "").includes(q)
      );
    });
  }, [rows, searchQuery, departmentFilter, statusFilter]);

  // Auto-selects the first (visible) row when nothing's been explicitly
  // clicked yet -- same convention as the Doctors page's own detail panel --
  // so the detail panel never starts on an empty "select someone" state
  // while the directory has at least one row to show.
  const selected = rows.find((s) => s.id === selectedId) || filteredRows[0] || null;
  const selectedIndex = selected ? rows.findIndex((s) => s.id === selected.id) : 0;

  const attendanceByStaffId = useMemo(
    () => new Map((attendanceToday || []).map((r) => [r.staff_id, r])),
    [attendanceToday],
  );
  const selectedTodayAttendance = selected ? (attendanceByStaffId.get(selected.id) ?? null) : null;
  // Real check-in/out data (useAttendanceOverview), not the old manual
  // attendance_status toggle -- "absent" here means no check-in row today,
  // same definition db.get_hospital_attendance() itself uses.
  const absentTodayCount = attendanceToday
    ? attendanceToday.filter((r) => r.status === "absent").length
    : null;
  // department_name, not department_id -- a doctor-role row's department
  // comes via doctor_id -> doctors.department_id (department_id itself is
  // always null there by design), so counting department_id alone would
  // silently ignore every doctor's department.
  const departmentsCovered = new Set(rows.map((s) => s.department_name).filter(Boolean)).size;

  return (
    <PortalShell hospital={hospital} active="staff">
      <PageHeader
        title="Staff"
        description={formatHeaderDate(today)}
      />

      {!ready || !canView ? (
        !ready ? null : (
          <p className="text-ink-400 text-[13px]">
            You don&apos;t have access to Staff Management.
          </p>
        )
      ) : (
        <>
          {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

          <div className="mb-space-4 gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="Total Staff"
              value={staff ? staff.length : null}
              deltaPct={null}
              hint="Live count"
              icon={Users}
            />
            <StatTile
              label="Active Staff"
              value={staff ? staff.filter((s) => s.is_active).length : null}
              deltaPct={null}
              hint={staff ? `of ${staff.length} total` : ""}
              icon={UserCheck}
            />
            <StatTile
              label="Absent Today"
              value={canViewAttendance ? absentTodayCount : null}
              deltaPct={null}
              hint={canViewAttendance ? "No check-in yet" : "No access"}
              icon={CalendarX}
              tint="clay"
            />
            <StatTile
              label="Departments"
              value={staff ? departmentsCovered : null}
              deltaPct={null}
              hint="Live count"
              icon={Building2}
            />
          </div>

          <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
            <div className="lg:col-span-2">
              <Card className="p-space-4">
                <div className="mb-space-3 gap-space-3 flex flex-wrap items-start justify-between">
                  <div>
                    <h3 className="text-label text-ink-900 font-bold">Staff Directory</h3>
                    <p className="text-hint mt-space-1">
                      Manage hospital staff, view attendance and manage access.
                    </p>
                  </div>
                  <PermissionGate page="staff" action="write">
                    <Button size="md" onClick={() => setAddStaffOpen(true)}>
                      <Plus size={14} /> Add Staff
                    </Button>
                  </PermissionGate>
                </div>

                <div className="mb-space-3 gap-space-3 flex flex-wrap items-center">
                  <div className="relative min-w-50 flex-1">
                    <Search
                      size={14}
                      className="left-space-3 text-ink-400 pointer-events-none absolute top-1/2 -translate-y-1/2"
                    />
                    <input
                      type="text"
                      placeholder="Search by name, role, department or phone…"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="border-line bg-card pl-space-8 pr-space-3 text-ink-900 focus:border-brand-400 h-10 w-full rounded-md border text-[13px] outline-none"
                    />
                  </div>
                  <FilterSelect
                    value={departmentFilter}
                    onChange={setDepartmentFilter}
                    allLabel="All Departments"
                    options={departmentOptions}
                  />
                  <FilterSelect
                    value={statusFilter}
                    onChange={setStatusFilter}
                    allLabel="All Status"
                    options={STATUS_OPTIONS}
                  />
                </div>

                <DataTable
                  columns={createStaffColumns({
                    onSelect: (s) => setSelectedId(s.id),
                  })}
                  data={filteredRows}
                  getRowId={(s) => String(s.id)}
                  onRowClick={(s) => setSelectedId(s.id)}
                  rowClassName={(s) => (s.id === selected?.id ? "bg-brand-50" : "")}
                  pageSize={10}
                  pageSizeOptions={[10, 25, 50]}
                  loading={!staff}
                  emptyMessage={
                    staff && staff.length > 0
                      ? "No staff match your search/filters."
                      : "No staff members yet."
                  }
                />
              </Card>
            </div>

            <div>
              <StaffDetailPanel
                staff={selected}
                index={Math.max(selectedIndex, 0)}
                canManage={canManage}
                canViewAttendance={canViewAttendance}
                canViewLeaveHistory={canViewLeaveHistory}
                canManageLeave={canManageLeave}
                todayAttendance={selectedTodayAttendance}
                togglingId={togglingId}
                onToggleActive={handleToggleActive}
                onResetPassword={openResetPassword}
                onEdit={setEditingStaff}
                onViewAttendanceHistory={(s) => setAttendanceHistoryStaffId(s.id)}
                onViewLeaveHistory={(s) => setLeaveHistoryStaffId(s.id)}
                onManageLeave={setManageLeaveFor}
              />
            </div>
          </div>
        </>
      )}

      <AddStaffDialog open={addStaffOpen} onOpenChange={setAddStaffOpen} onCreated={load} />

      <EditStaffDialog
        staff={editingStaff}
        onOpenChange={(open) => {
          if (!open) setEditingStaff(null);
        }}
        onSaved={load}
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
        open={manageLeaveFor !== null}
        onOpenChange={(open) => {
          if (!open) setManageLeaveFor(null);
        }}
        subjectStaffId={manageLeaveFor?.id}
        subjectName={manageLeaveFor?.name}
        onCreated={load}
      />

      <Dialog
        open={resetPasswordTarget !== null}
        onOpenChange={(open) => {
          if (!open) closeResetPassword();
        }}
      >
        <DialogContent>
          <DialogTitle>
            Reset password{resetPasswordTarget ? ` for ${resetPasswordTarget.name}` : ""}
          </DialogTitle>
          <form onSubmit={handleResetPassword} className="gap-space-3 flex flex-col">
            <Field
              label="New password"
              htmlFor="reset_new_password"
              required
              hint="At least 8 characters."
            >
              <PasswordInput
                id="reset_new_password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
            </Field>
            <Field label="Confirm new password" htmlFor="reset_confirm_password" required>
              <PasswordInput
                id="reset_confirm_password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </Field>
            {resetErrors.length > 0 && (
              <ul className="pl-space-4 text-error list-disc text-[12.5px] font-medium">
                {resetErrors.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            )}
            <div className="gap-space-2 flex">
              <Button type="submit" disabled={resetStaffPassword.isPending} size="md">
                {resetStaffPassword.isPending ? "Resetting…" : "Reset password"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="md"
                onClick={closeResetPassword}
                disabled={resetStaffPassword.isPending}
              >
                Cancel
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </PortalShell>
  );
}
