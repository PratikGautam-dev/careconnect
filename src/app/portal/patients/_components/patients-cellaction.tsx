"use client";

import { useRouter } from "next/navigation";
import { Eye, MoreHorizontal, Trash2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PermissionGate } from "@/components/portal/PermissionGate";
import type { Patient } from "@/hooks/usePatients";

type PatientCellActionProps = {
  patient: Patient;
  onDelete: (patient: Patient) => void;
};

/** Combined actions menu (View Details / Delete). Stops propagation on its
 * own wrapper so opening the menu (or picking an item) doesn't also
 * trigger the row's onRowClick selection. "View Details" navigates
 * straight to the full /portal/patients/[id] record, distinct from
 * row-click/the name link which open the page's own side panel instead. */
export function PatientCellAction({ patient, onDelete }: PatientCellActionProps) {
  const router = useRouter();
  return (
    <div onClick={(e) => e.stopPropagation()}>
      <DropdownMenu>
        <DropdownMenuTrigger
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-ink-600 hover:bg-black/4 hover:text-ink-900"
          aria-label={`Actions for ${patient.name || patient.phone}`}
        >
          <MoreHorizontal size={16} />
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuGroup>
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            <DropdownMenuItem onClick={() => router.push(`/portal/patients/${patient.id}`)}>
              <Eye size={14} /> View Details
            </DropdownMenuItem>
            <PermissionGate page="patients" action="delete">
              <DropdownMenuItem variant="destructive" onClick={() => onDelete(patient)}>
                <Trash2 size={14} /> Delete
              </DropdownMenuItem>
            </PermissionGate>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
