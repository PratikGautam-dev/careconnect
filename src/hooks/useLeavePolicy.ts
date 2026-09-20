import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { staffFetch } from "@/lib/staffAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";

export type LeavePolicy = {
  doctor_annual_leave_days: number;
  staff_annual_leave_days: number;
  leave_types: string[];
};

/** Settings page's "Leave policy" card -- the portal-admin-configurable
 * annual leave allowance (doctor/receptionist only, confirmed with the
 * user) that leave balances (Staff/Doctors detail panels) are computed
 * against, plus leave_types: the names staff can pick from when submitting
 * a leave request (Holiday Application / the admin's own "New leave
 * request"), replacing what used to be a fixed 6-value list. Its own small
 * load/save cycle, independent of the big usePortalSettings() form -- same
 * self-contained-manager shape as useLabServiceAreas.ts, since GET/POST
 * /api/portal/leave-requests/policy is its own endpoint, not part of that
 * big PATCH. */
export function useLeavePolicy(ready: boolean) {
  const router = useRouter();

  const {
    data: policy,
    error: queryError,
  } = useQuery({
    queryKey: ["portal-leave-policy"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await staffFetch("/api/portal/leave-requests/policy");
      return unwrapPortalResult<LeavePolicy>(router, result);
    },
  });

  // Editable draft, seeded once per successful load -- edits here shouldn't
  // be clobbered by a background refetch of the same query.
  const [seeded, setSeeded] = useState(false);
  const [doctorDays, setDoctorDays] = useState("");
  const [staffDays, setStaffDays] = useState("");
  const [leaveTypes, setLeaveTypes] = useState<string[]>([]);
  if (policy && !seeded) {
    setSeeded(true);
    setDoctorDays(String(policy.doctor_annual_leave_days));
    setStaffDays(String(policy.staff_annual_leave_days));
    setLeaveTypes(policy.leave_types);
  }

  const saveMutation = useMutation({
    mutationFn: async (payload: LeavePolicy) => {
      const result = await staffFetch("/api/portal/leave-requests/policy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapPortalResult<LeavePolicy>(router, result);
    },
  });

  function addLeaveType(name: string) {
    const trimmed = name.trim();
    if (!trimmed || leaveTypes.some((t) => t.toLowerCase() === trimmed.toLowerCase())) return;
    setLeaveTypes((prev) => [...prev, trimmed]);
  }

  function removeLeaveType(name: string) {
    setLeaveTypes((prev) => prev.filter((t) => t !== name));
  }

  const [saveError, setSaveError] = useState<string | null>(null);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaveError(null);
    try {
      const data = await saveMutation.mutateAsync({
        doctor_annual_leave_days: Number(doctorDays),
        staff_annual_leave_days: Number(staffDays),
        leave_types: leaveTypes,
      });
      setLeaveTypes(data.leave_types);
      toast.success("Leave policy updated");
    } catch (err) {
      if (isPortalMutationError(err)) {
        setSaveError(err.message);
        toast.error("Couldn't save leave policy", err.message);
      }
    }
  }

  return {
    policy: policy ?? null,
    doctorDays,
    setDoctorDays,
    staffDays,
    setStaffDays,
    leaveTypes,
    addLeaveType,
    removeLeaveType,
    saving: saveMutation.isPending,
    error: saveError ?? (queryError ? "Couldn't load leave policy — try again." : null),
    handleSave,
  };
}
