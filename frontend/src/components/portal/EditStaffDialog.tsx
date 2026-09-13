"use client";

import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { SectionHeader } from "./SectionHeader";
import { StaffContactFields } from "./StaffContactFields";
import { useEditStaff } from "@/hooks/useEditStaff";
import type { StaffMember } from "@/hooks/useStaffManagement";

type Props = {
  /** null closes the dialog -- there's nothing to edit. */
  staff: StaffMember | null;
  onOpenChange: (open: boolean) => void;
  onSaved?: () => void;
};

/** Reusable "Edit staff details" modal -- Name plus the shared
 * StaffContactFields (Phone/Address/Department/Working schedule/Reports-to).
 * Role and the linked doctor aren't editable here -- there's no repository
 * support for reassigning either yet (update_staff_user_role() is a
 * separate, unrelated concern this dialog doesn't touch), same one-way
 * choice the create form's own role picker already makes. */
export function EditStaffDialog({ staff, onOpenChange, onSaved }: Props) {
  const {
    departments, staffOptions,
    name, setName, phone, setPhone, address, setAddress, departmentId, setDepartmentId, schedule, setSchedule,
    reportsToId, setReportsToId,
    formError, saving, handleSave,
  } = useEditStaff(staff, onOpenChange, onSaved);

  return (
    <Dialog open={staff !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Edit staff details</DialogTitle>
        {staff && (
          <form onSubmit={handleSave} className="mt-space-3 grid grid-cols-1 gap-space-3 md:grid-cols-2">
            <div className="md:col-span-2">
              <SectionHeader title="Account" description="This staff member's name -- role isn't editable here." />
            </div>
            <Field label="Name" htmlFor="edit_staff_name">
              <Input id="edit_staff_name" value={name} onChange={(e) => setName(e.target.value)} required />
            </Field>
            <Field label="Role" htmlFor="edit_staff_role" hint="Not editable here.">
              <Input id="edit_staff_role" value={staff.role_name} disabled />
            </Field>
            <div className="mt-space-2 border-t border-line pt-space-4 md:col-span-2">
              <SectionHeader
                title="Profile information"
                description="Contact details, department and who they report to -- shown on their staff profile."
              />
            </div>
            <StaffContactFields
              hasLinkedDoctor={staff.is_doctor_role}
              phone={phone} setPhone={setPhone}
              address={address} setAddress={setAddress}
              departmentId={departmentId} setDepartmentId={setDepartmentId} departments={departments}
              schedule={schedule} setSchedule={setSchedule}
              reportsToId={reportsToId} setReportsToId={setReportsToId} staffOptions={staffOptions}
              excludeStaffId={staff.id}
            />
            {formError && <p className="text-[12.5px] font-medium text-error md:col-span-2">{formError}</p>}
            <div className="md:col-span-2">
              <Button type="submit" disabled={saving || !name} size="md">
                {saving ? "Saving…" : "Save changes"}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
