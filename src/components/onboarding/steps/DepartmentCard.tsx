import { Plus, Trash2 } from "lucide-react";
import { Input } from "@/components/ui/Input";
import { DepartmentForm } from "../types";
import type { WizardDispatch } from "../useWizardState";
import { DoctorCard } from "./DoctorCard";

type Props = {
  deptIndex: number;
  department: DepartmentForm;
  dispatch: WizardDispatch;
};

export function DepartmentCard({ deptIndex, department, dispatch }: Props) {
  return (
    <div className="mb-space-4 border-line bg-card p-space-4 rounded-lg border shadow-[var(--shadow-sm)]">
      <div className="mb-space-3 gap-space-3 flex items-center">
        <Input
          placeholder="Department name"
          value={department.name}
          onChange={(e) => dispatch({ type: "setDepartmentName", deptIndex, name: e.target.value })}
          className="max-w-sm font-semibold"
        />
        <button
          type="button"
          onClick={() => dispatch({ type: "removeDepartment", deptIndex })}
          className="text-error ml-auto flex shrink-0 items-center gap-1 text-[12.5px] font-semibold hover:underline"
        >
          <Trash2 size={13} /> Remove department
        </button>
      </div>

      <div className="space-y-space-3">
        {department.doctors.map((doctor, docIndex) => (
          <DoctorCard
            key={docIndex}
            deptIndex={deptIndex}
            docIndex={docIndex}
            doctor={doctor}
            dispatch={dispatch}
          />
        ))}
      </div>

      <button
        type="button"
        onClick={() => dispatch({ type: "addDoctor", deptIndex })}
        className="mt-space-3 text-brand-600 flex items-center gap-1 text-[13px] font-semibold hover:underline"
      >
        <Plus size={14} /> Add doctor
      </button>
    </div>
  );
}
