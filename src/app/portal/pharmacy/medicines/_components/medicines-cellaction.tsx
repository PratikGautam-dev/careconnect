"use client";

import { Pencil, MoreHorizontal, Power } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Medicine } from "@/hooks/usePharmacyMedicines";

export function MedicineCellAction({
  medicine, onEdit, onToggleActive,
}: {
  medicine: Medicine;
  onEdit: (medicine: Medicine) => void;
  onToggleActive: (medicine: Medicine) => void;
}) {
  return (
    <div onClick={(e) => e.stopPropagation()}>
      <DropdownMenu>
        <DropdownMenuTrigger
          className="text-ink-600 hover:text-ink-900 inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-black/4"
          aria-label={`Actions for ${medicine.name}`}
        >
          <MoreHorizontal size={16} />
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuGroup>
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            <DropdownMenuItem onClick={() => onEdit(medicine)}>
              <Pencil size={14} /> Edit
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onToggleActive(medicine)}>
              <Power size={14} /> {medicine.is_active ? "Deactivate" : "Activate"}
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
