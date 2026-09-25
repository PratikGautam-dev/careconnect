"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { useLeavePolicy } from "@/hooks/useLeavePolicy";

/** Settings page's "Leave policy" card -- the two numbers a leave balance
 * (Staff/Doctors detail panels, Leave Requests page) is computed against,
 * plus the list of leave type names staff can pick from when submitting a
 * request (Holiday Application / the admin's own "New leave request").
 * Doctor/receptionist only for the day counts -- admin approves leave,
 * doesn't accrue an allowance, so there's no third field here for it;
 * leave types apply to everyone regardless of role. */
export function LeavePolicyManager({ canManage }: { canManage: boolean }) {
  const {
    policy,
    doctorDays,
    setDoctorDays,
    staffDays,
    setStaffDays,
    leaveTypes,
    addLeaveType,
    removeLeaveType,
    saving,
    error,
    handleSave,
  } = useLeavePolicy(true);
  const [newType, setNewType] = useState("");

  if (!policy) return <p className="text-ink-400 text-[13px]">Loading…</p>;

  function handleAddType() {
    addLeaveType(newType);
    setNewType("");
  }

  return (
    <form onSubmit={handleSave} className="gap-space-3 flex flex-col">
      <div className="gap-x-space-4 grid grid-cols-1 sm:grid-cols-2">
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
        <Field
          label="Staff annual leave (days)"
          htmlFor="staff_annual_leave_days"
          hint="Receptionists only -- admin doesn't accrue leave."
        >
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

      <Field
        label="Leave types"
        htmlFor="new_leave_type"
        hint="Shown to staff when they submit a leave request."
      >
        {leaveTypes.length > 0 && (
          <div className="mb-space-2 gap-space-2 flex flex-wrap">
            {leaveTypes.map((t) => (
              <span
                key={t}
                className="gap-space-1 pl-space-3 pr-space-2 py-space-1 text-ink-700 flex items-center rounded-full bg-black/4 text-[12.5px] font-medium"
              >
                {t}
                {canManage && (
                  <button
                    type="button"
                    onClick={() => removeLeaveType(t)}
                    aria-label={`Remove ${t}`}
                    className="text-ink-400 hover:text-error"
                  >
                    <X size={12} />
                  </button>
                )}
              </span>
            ))}
          </div>
        )}
        {canManage && (
          <div className="gap-space-2 flex">
            <Input
              id="new_leave_type"
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleAddType();
                }
              }}
              placeholder="e.g. Bereavement Leave"
            />
            <Button
              type="button"
              variant="secondary"
              onClick={handleAddType}
              disabled={!newType.trim()}
            >
              Add
            </Button>
          </div>
        )}
      </Field>

      {error && <p className="text-error text-[12.5px] font-medium">{error}</p>}
      {canManage && (
        <Button type="submit" size="md" disabled={saving} className="self-start">
          {saving ? "Saving…" : "Save leave policy"}
        </Button>
      )}
    </form>
  );
}
