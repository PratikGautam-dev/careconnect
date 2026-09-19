import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";

export type LeavePolicy = { doctor_annual_leave_days: number; staff_annual_leave_days: number };

/** Settings page's "Leave policy" card -- the portal-admin-configurable
 * annual leave allowance (doctor/receptionist only, confirmed with the
 * user) that leave balances (Staff/Doctors detail panels) are computed
 * against. Its own small load/save cycle, independent of the big
 * usePortalSettings() form -- same self-contained-manager shape as
 * useLabServiceAreas.ts, since GET/POST /api/portal/leave-requests/policy
 * is its own endpoint, not part of that big PATCH. */
export function useLeavePolicy(ready: boolean) {
  const router = useRouter();
  const [policy, setPolicy] = useState<LeavePolicy | null>(null);
  const [doctorDays, setDoctorDays] = useState("");
  const [staffDays, setStaffDays] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/portal/leave-requests/policy");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    const data = result.data as LeavePolicy;
    setPolicy(data);
    setDoctorDays(String(data.doctor_annual_leave_days));
    setStaffDays(String(data.staff_annual_leave_days));
  }, [router]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    const result = await staffFetch("/api/portal/leave-requests/policy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        doctor_annual_leave_days: Number(doctorDays),
        staff_annual_leave_days: Number(staffDays),
      }),
    });
    setSaving(false);
    if (!result.ok) {
      if (result.unauthorized) {
        router.push("/portal/login");
        return;
      }
      setError(result.error);
      toast.error("Couldn't save leave policy", result.error);
      return;
    }
    setPolicy(result.data as LeavePolicy);
    toast.success("Leave policy updated");
  }

  return { policy, doctorDays, setDoctorDays, staffDays, setStaffDays, saving, error, handleSave };
}
