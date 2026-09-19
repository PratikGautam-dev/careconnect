"use client";

import { Eye, KeyRound, MoreHorizontal, Power } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { StaffRow } from "./staff-columns";

type Props = {
  staff: StaffRow;
  canManage: boolean;
  togglingId: number | null;
  onSelect: (staff: StaffRow) => void;
  onToggleActive: (staff: StaffRow) => void;
  onResetPassword: (staff: StaffRow) => void;
};

export function StaffCellAction({ staff, canManage, togglingId, onSelect, onToggleActive, onResetPassword }: Props) {
  return (
    <div onClick={(e) => e.stopPropagation()}>
      <DropdownMenu>
        <DropdownMenuTrigger
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-ink-600 hover:bg-black/4 hover:text-ink-900"
          aria-label={`Actions for ${staff.name}`}
        >
          <MoreHorizontal size={16} />
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuGroup>
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            <DropdownMenuItem onClick={() => onSelect(staff)}>
              <Eye size={14} /> View details
            </DropdownMenuItem>
            {canManage && (
              <>
                <DropdownMenuItem onClick={() => onResetPassword(staff)}>
                  <KeyRound size={14} /> Reset password
                </DropdownMenuItem>
                <DropdownMenuItem disabled={togglingId === staff.id} onClick={() => onToggleActive(staff)}>
                  <Power size={14} /> {staff.is_active ? "Deactivate" : "Activate"}
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
