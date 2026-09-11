import { useEffect, useState } from "react";
import { staffFetch } from "@/lib/staffAuth";

export type Department = { id: string; name: string };

/** Lightweight departments-only fetch, reusing the same /api/portal/doctors
 * response the Doctors page already fetches from (its own department list
 * lives there -- there's no separate departments-only endpoint) and just
 * picking out `departments`, ignoring the doctors/on_leave_today_count it
 * also returns. Used by the Staff page/dialogs for a non-doctor staff
 * member's own department field. */
export function useDepartments(ready: boolean) {
  const [departments, setDepartments] = useState<Department[] | null>(null);

  useEffect(() => {
    if (!ready) return;
    staffFetch("/api/portal/doctors").then((result) => {
      if (!result.ok) return;
      const data = result.data as { departments: Department[] };
      setDepartments(data.departments || []);
    });
  }, [ready]);

  return departments;
}
