import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalFetch } from "@/lib/portalAuth";
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
  // Migration 20260919080000: replaces a fixed "HH:MM" cutoff (couldn't
  // correctly serve two staff on different shifts) with a GRACE PERIOD
  // applied on top of each staff member's OWN shift end (StaffDetail.
  // working_hours, falling back to attendance_shift_end when unset).
  // null/"" means auto-checkout is off -- no code-level default, same
  // "NULL means no cap" convention as max_appointments_per_day.
  attendance_auto_checkout_grace_minutes: number | "";
  /** Read-only -- the caller's own IP as the backend sees it right now
   * (core/rate_limit.py's client_ip()), so a non-technical admin standing
   * on the hospital's own WiFi can whitelist it without reading server
   * logs or an external "what's my IP" site. Never sent back on save. */
  detected_ip: string | null;
};

/** Loads + saves Settings -> Attendance's geofence/IP/shift-window policy
 * -- a separate endpoint (/api/portal/settings/attendance) and hook from
 * usePortalSettings, gated by the real "attendance_settings" page_key
 * (admin-only by default) rather than folded into that shared, hospital-
 * only-authenticated, full-object General settings save. */
export function useAttendanceSettings(ready: boolean) {
  const router = useRouter();
  const [settings, setSettings] = useState<AttendanceSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    const result = await portalFetch("/api/portal/settings/attendance");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    // attendance_auto_checkout_grace_minutes comes back as `null` when
    // unset (no default to fall back to) -- coerced to "" here so the
    // numeric <Input> below never renders "null", same convention
    // usePortalSettings.ts's own max_appointments_per_day uses.
    const data = result.data as AttendanceSettings & { attendance_auto_checkout_grace_minutes: number | null };
    setSettings({ ...data, attendance_auto_checkout_grace_minutes: data.attendance_auto_checkout_grace_minutes ?? "" });
  }, [router]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    setSaved(false);
    setError(null);
    const result = await portalFetch("/api/portal/settings/attendance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    if (!result.ok) {
      setSaving(false);
      if (result.unauthorized) router.push("/portal/login");
      else {
        setError(result.error);
        toast.error("Couldn't save attendance settings", result.error);
      }
      return;
    }
    await load();
    setSaving(false);
    setSaved(true);
    toast.success("Attendance settings saved");
  }

  return { settings, setSettings, error, saving, saved, handleSave };
}
