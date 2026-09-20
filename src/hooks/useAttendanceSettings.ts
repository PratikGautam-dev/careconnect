import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";

export type AttendanceSettings = {
  attendance_latitude: number | null;
  attendance_longitude: number | null;
  attendance_allowed_radius_meters: number;
  attendance_allowed_ip_cidrs: string;
  attendance_shift_start: string;
  attendance_shift_end: string;
  attendance_early_checkin_minutes: number;
  attendance_late_threshold_minutes: number;
  // A GRACE PERIOD applied on top of each staff member's OWN shift end
  // (StaffDetail.working_hours, falling back to attendance_shift_end when
  // unset) -- correctly serves staff on different shifts, unlike a fixed
  // "HH:MM" cutoff. null/"" means auto-checkout is off.
  attendance_auto_checkout_grace_minutes: number | "";
  /** Read-only -- the caller's own IP as the backend sees it right now
   * (core/rate_limit.py's client_ip()), so a non-technical admin standing
   * on the hospital's own WiFi can whitelist it without reading server
   * logs or an external "what's my IP" site. Never sent back on save. */
  detected_ip: string | null;
};

function normalizeSettings(
  data: AttendanceSettings & { attendance_auto_checkout_grace_minutes: number | null },
): AttendanceSettings {
  // attendance_auto_checkout_grace_minutes comes back as `null` when unset
  // (no default to fall back to) -- coerced to "" here so the numeric
  // <Input> below never renders "null", same convention usePortalSettings.ts's
  // own max_appointments_per_day uses.
  return {
    ...data,
    attendance_auto_checkout_grace_minutes: data.attendance_auto_checkout_grace_minutes ?? "",
  };
}

/** Loads + saves Settings -> Attendance's geofence/IP/shift-window policy
 * -- a separate endpoint (/api/portal/settings/attendance) and hook from
 * usePortalSettings, gated by the real "attendance_settings" page_key
 * (admin-only by default) rather than folded into that shared, hospital-
 * only-authenticated, full-object General settings save. Single page,
 * single consumer -- kept as one hook (like useEditTenant) rather than
 * separated into per-mutation hooks nothing else would import. */
export function useAttendanceSettings(ready: boolean) {
  const router = useRouter();

  const {
    data: loadedSettings,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey: ["portal-attendance-settings"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/settings/attendance");
      const data = unwrapPortalResult<
        AttendanceSettings & { attendance_auto_checkout_grace_minutes: number | null }
      >(router, result);
      return normalizeSettings(data);
    },
  });

  // Local draft, seeded once per successful load -- edits here (via
  // setSettings) shouldn't be clobbered by a background refetch of the same
  // query, same "editable draft over a query result" shape usePatientDetail's
  // demographics fields use.
  const [seeded, setSeeded] = useState(false);
  const [settings, setSettings] = useState<AttendanceSettings | null>(null);
  if (loadedSettings && !seeded) {
    setSeeded(true);
    setSettings(loadedSettings);
  }

  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: async (payload: AttendanceSettings) => {
      const result = await portalFetch("/api/portal/settings/attendance", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setSaved(false);
    setSaveError(null);
    try {
      await saveMutation.mutateAsync(settings);
      await refetch();
      setSaved(true);
      toast.success("Attendance settings saved");
    } catch (err) {
      if (isPortalMutationError(err)) {
        setSaveError(err.message);
        toast.error("Couldn't save attendance settings", err.message);
      }
    }
  }

  return {
    settings,
    setSettings,
    error: saveError ?? (queryError ? "Couldn't load attendance settings — try again." : null),
    saving: saveMutation.isPending,
    saved,
    handleSave,
  };
}
