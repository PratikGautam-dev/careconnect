import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import type { Department } from "@/hooks/useDepartments";
import type { StaffOption } from "@/hooks/useAddStaff";
import { SectionHeader } from "./SectionHeader";
import { WorkingScheduleFields, type WorkingScheduleValue } from "./WorkingScheduleFields";

type Props = {
  /** Whether a doctor profile is currently linked (doctor_id set) --
   * independent of role entirely (dynamic-roles migration: any role can
   * optionally have a doctor linked). Hides the Department picker in that
   * case, since the doctor's own profile already supplies it. */
  hasLinkedDoctor: boolean;
  phone: string;
  setPhone: (v: string) => void;
  address: string;
  setAddress: (v: string) => void;
  departmentId: string;
  setDepartmentId: (v: string) => void;
  departments: Department[] | null;
  schedule: WorkingScheduleValue;
  setSchedule: (v: WorkingScheduleValue) => void;
  reportsToId: string;
  setReportsToId: (v: string) => void;
  staffOptions: StaffOption[];
  /** Edit mode only -- the staff member being edited can't report to
   * themselves (also enforced by the DB's own CHECK constraint). */
  excludeStaffId?: number;
};

/** Phone/Address/Department/Working schedule/Reports-to -- the fields
 * AddStaffDialog and EditStaffDialog share (both create/edit the same
 * staff_details columns); Name/Email/Password/Role/Doctor stay in each
 * dialog since they differ enough (Edit has no password, can't change
 * role/doctor). Working schedule (Staff schedule feature) replaces the old
 * single day/evening/night Shift dropdown with the same WorkingScheduleFields
 * days+times+breaks picker doctors use. */
export function StaffContactFields({
  hasLinkedDoctor,
  phone,
  setPhone,
  address,
  setAddress,
  departmentId,
  setDepartmentId,
  departments,
  schedule,
  setSchedule,
  reportsToId,
  setReportsToId,
  staffOptions,
  excludeStaffId,
}: Props) {
  return (
    <>
      <Field label="Phone" htmlFor="staff_phone">
        <Input id="staff_phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
      </Field>
      <Field label="Address" htmlFor="staff_address">
        <Input id="staff_address" value={address} onChange={(e) => setAddress(e.target.value)} />
      </Field>
      {!hasLinkedDoctor && (
        <Field
          label="Department"
          htmlFor="staff_department"
          hint="A doctor's department comes from their linked doctor profile instead."
        >
          <select
            id="staff_department"
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
            className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13px]"
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
      <Field label="Reports to" htmlFor="staff_reports_to">
        <select
          id="staff_reports_to"
          value={reportsToId}
          onChange={(e) => setReportsToId(e.target.value)}
          className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13px]"
        >
          <option value="">Nobody set</option>
          {staffOptions
            .filter((s) => s.id !== excludeStaffId)
            .map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
        </select>
      </Field>
      <div className="mt-space-3 border-line pt-space-4 border-t md:col-span-2">
        <SectionHeader
          title="Schedule"
          description="Which days this staff member works, and their shift timings."
        />
        <WorkingScheduleFields value={schedule} onChange={setSchedule} />
      </div>
    </>
  );
}
