import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import type { Department } from "@/hooks/useDepartments";
import type { StaffOption } from "@/hooks/useAddStaff";
import type { Shift } from "@/hooks/useStaffManagement";
import type { StaffRole } from "@/lib/staffAuth";

const SHIFT_OPTIONS: { value: Shift; label: string }[] = [
  { value: "day", label: "Day (8AM - 4PM)" },
  { value: "evening", label: "Evening (4PM - 12AM)" },
  { value: "night", label: "Night (8PM - 8AM)" },
];

type Props = {
  role: StaffRole;
  phone: string;
  setPhone: (v: string) => void;
  address: string;
  setAddress: (v: string) => void;
  departmentId: string;
  setDepartmentId: (v: string) => void;
  departments: Department[] | null;
  shift: Shift | "";
  setShift: (v: Shift | "") => void;
  reportsToId: string;
  setReportsToId: (v: string) => void;
  staffOptions: StaffOption[];
  /** Edit mode only -- the staff member being edited can't report to
   * themselves (also enforced by the DB's own CHECK constraint). */
  excludeStaffId?: number;
};

/** Phone/Address/Department/Shift/Reports-to -- the fields AddStaffDialog
 * and EditStaffDialog share (both create/edit the same staff_details
 * columns); Name/Email/Password/Role/Doctor stay in each dialog since they
 * differ enough (Edit has no password, can't change role/doctor). */
export function StaffContactFields({
  role, phone, setPhone, address, setAddress, departmentId, setDepartmentId, departments,
  shift, setShift, reportsToId, setReportsToId, staffOptions, excludeStaffId,
}: Props) {
  return (
    <>
      <Field label="Phone" htmlFor="staff_phone">
        <Input id="staff_phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
      </Field>
      <Field label="Address" htmlFor="staff_address">
        <Input id="staff_address" value={address} onChange={(e) => setAddress(e.target.value)} />
      </Field>
      {role !== "doctor" && (
        <Field label="Department" htmlFor="staff_department" hint="A doctor's department comes from their linked doctor profile instead.">
          <select
            id="staff_department"
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
            className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-900"
          >
            <option value="">No department</option>
            {(departments || []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </Field>
      )}
      <Field label="Shift" htmlFor="staff_shift">
        <select
          id="staff_shift"
          value={shift}
          onChange={(e) => setShift(e.target.value as Shift | "")}
          className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-900"
        >
          <option value="">No shift set</option>
          {SHIFT_OPTIONS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Reports to" htmlFor="staff_reports_to">
        <select
          id="staff_reports_to"
          value={reportsToId}
          onChange={(e) => setReportsToId(e.target.value)}
          className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-900"
        >
          <option value="">Nobody set</option>
          {staffOptions.filter((s) => s.id !== excludeStaffId).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </Field>
    </>
  );
}
