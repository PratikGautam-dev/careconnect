"use client";

import { Eye, MoreHorizontal, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
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

/** Single combined actions menu (View Details / Delete) -- replaces the two
 * separate trailing columns the hand-rolled table used to render. Stops
 * propagation on its own wrapper so opening the menu (or picking an item in
 * it) doesn't also trigger the row's own onRowClick navigation. */
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
