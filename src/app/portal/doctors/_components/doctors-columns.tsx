"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Mail, Phone } from "lucide-react";
// Row-level "..." actions menu is commented out below -- View profile/Edit/
// Mark available-unavailable all now live in DoctorDetailPanel.tsx's own
// Quick Actions instead of being duplicated here.
// import { Eye, MoreHorizontal, Pencil, Power } from "lucide-react";
// import {
//   DropdownMenu,
//   DropdownMenuContent,
//   DropdownMenuGroup,
//   DropdownMenuItem,
//   DropdownMenuLabel,
//   DropdownMenuTrigger,
// } from "@/components/ui/dropdown-menu";
import { AVATAR_TINTS } from "@/lib/avatarTints";
import { cn } from "@/lib/cn";
import type { Doctor } from "@/hooks/useDoctors";

export { AVATAR_TINTS };

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
}

type CreateDoctorColumnsOptions = {
  onSelect: (doc: Doctor) => void;
  // Only used by the commented-out "actions" column below.
  // canManage: boolean;
  // togglingId: string | null;
  // onToggleActive: (doc: Doctor) => void;
  // loadingDoctorForEdit: string | null;
  // onEdit: (doc: Doctor) => void;
};

/** Column definitions for the /portal/doctors DataTable. Availability only
 * reflects the real is_active flag (Available/Unavailable) -- there's no
 * real-time presence tracking, so finer states like In Consultation aren't
 * shown. Contact's email row shows login_email (null until a login is
 * created). Leave Balance shows "—" for a doctor with no login yet, since
 * there's no identity to attach a leave request to. */
export function createDoctorColumns({ onSelect }: CreateDoctorColumnsOptions): ColumnDef<Doctor>[] {
  return [
    {
      id: "employee_id",
      header: "Employee ID",
      cell: ({ row }) => <span className="text-ink-600">{row.original.employee_id || "—"}</span>,
    },
    {
      id: "doctor",
      header: "Doctor",
      cell: ({ row }) => {
        const d = row.original;
        return (
          <button
            type="button"
            onClick={() => onSelect(d)}
            className="gap-space-2 flex items-center text-left"
          >
            <span
              className={cn(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[12px] font-bold",
                AVATAR_TINTS[row.index % AVATAR_TINTS.length],
              )}
            >
              {initials(d.name)}
            </span>
            <div className="min-w-0">
              <p className="text-ink-900 truncate font-semibold">{d.name}</p>
              {d.qualification && (
                <p className="text-ink-400 truncate text-[11.5px]">{d.qualification}</p>
              )}
            </div>
          </button>
        );
      },
    },
    {
      id: "specialization",
      header: "Specialization",
      cell: ({ row }) => <span className="text-ink-600">{row.original.specialization || "—"}</span>,
    },
    {
      id: "department_name",
      header: "Department",
      cell: ({ row }) => <span className="text-ink-600">{row.original.department_name}</span>,
    },

    {
      id: "leave_balance",
      header: "Leave Balance",
      cell: ({ row }) => {
        const d = row.original;
        if (d.leave_balance_total == null) return <span className="text-ink-400">—</span>;
        return (
          <span className="text-ink-600">
            {d.leave_balance_total - (d.leave_balance_used ?? 0)} / {d.leave_balance_total} days
          </span>
        );
      },
    },
    {
      id: "availability",
      header: "Availability",
      cell: ({ row }) => (
        <span
          className={cn(
            "px-space-2 rounded-full py-0.5 text-[11px] font-semibold",
            row.original.is_active ? "bg-success-tint text-success" : "text-ink-600 bg-black/4",
          )}
        >
          {row.original.is_active ? "Available" : "Unavailable"}
        </span>
      ),
    },
    {
      id: "contact",
      header: "Contact",
      cell: ({ row }) => {
        const d = row.original;
        return (
          <div className="space-y-0.5 text-[12px]">
            <p className="text-ink-600 flex items-center gap-1">
              <Phone size={11} /> {d.phone || "—"}
            </p>
            <p className="text-ink-600 flex items-center gap-1">
              <Mail size={11} /> {d.login_email || "No login yet"}
            </p>
          </div>
        );
      },
    },
    // Row-level "..." actions menu -- View profile/Edit/Mark available-
    // unavailable all moved into the detail panel's own Quick Actions
    // instead (DoctorDetailPanel.tsx), so this duplicate per-row menu is
    // retired here rather than deleted outright.
    // {
    //   id: "actions",
    //   enableHiding: false,
    //   header: "Actions",
    //   cell: ({ row }) => {
    //     const d = row.original;
    //     return (
    //       <div onClick={(e) => e.stopPropagation()}>
    //         <DropdownMenu>
    //           <DropdownMenuTrigger
    //             className="text-ink-600 hover:text-ink-900 inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-black/4"
    //             aria-label={`Actions for ${d.name}`}
    //           >
    //             <MoreHorizontal size={16} />
    //           </DropdownMenuTrigger>
    //           <DropdownMenuContent>
    //             <DropdownMenuGroup>
    //               <DropdownMenuLabel>Actions</DropdownMenuLabel>
    //               <DropdownMenuItem onClick={() => onSelect(d)}>
    //                 <Eye size={14} /> View profile
    //               </DropdownMenuItem>
    //               {canManage && (
    //                 <>
    //                   <DropdownMenuItem
    //                     disabled={loadingDoctorForEdit === d.id}
    //                     onClick={() => onEdit(d)}
    //                   >
    //                     <Pencil size={14} /> Edit
    //                   </DropdownMenuItem>
    //                   <DropdownMenuItem
    //                     disabled={togglingId === d.id}
    //                     onClick={() => onToggleActive(d)}
    //                   >
    //                     <Power size={14} /> Mark {d.is_active ? "unavailable" : "available"}
    //                   </DropdownMenuItem>
    //                 </>
    //               )}
    //             </DropdownMenuGroup>
    //           </DropdownMenuContent>
    //         </DropdownMenu>
    //       </div>
    //     );
    //   },
    // },
  ];
}
