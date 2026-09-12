"use client";

import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { useLeavePolicy } from "@/hooks/useLeavePolicy";

/** Settings page's "Leave policy" card -- the two numbers a leave balance
 * (Staff/Doctors detail panels, Leave Requests page) is computed against.
 * Doctor/receptionist only -- admin approves leave, doesn't accrue an
 * allowance, so there's no third field here for it. */
export function LeavePolicyManager({ canManage }: { canManage: boolean }) {
  const { policy, doctorDays, setDoctorDays, staffDays, setStaffDays, saving, error, handleSave } = useLeavePolicy(true);

  if (!policy) return <p className="text-[13px] text-ink-400">Loading…</p>;

  return (
    <form onSubmit={handleSave} className="flex flex-col gap-space-3">
      <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
        <Field label="Doctor annual leave (days)" htmlFor="doctor_annual_leave_days">
          <Input
            id="doctor_annual_leave_days"
            type="number"
            min={0}
            value={doctorDays}
            onChange={(e) => setDoctorDays(e.target.value)}
            disabled={!canManage}
          />
        </Field>
        <Field label="Staff annual leave (days)" htmlFor="staff_annual_leave_days" hint="Receptionists only -- admin doesn't accrue leave.">
          <Input
            id="staff_annual_leave_days"
            type="number"
            min={0}
            value={staffDays}
            onChange={(e) => setStaffDays(e.target.value)}
            disabled={!canManage}
          />
        </Field>
      </div>
      {error && <p className="text-[12.5px] font-medium text-error">{error}</p>}
      {canManage && (
        <Button type="submit" size="md" disabled={saving} className="self-start">
          {saving ? "Saving…" : "Save leave policy"}
        </Button>
      )}
    </form>
  );
}
