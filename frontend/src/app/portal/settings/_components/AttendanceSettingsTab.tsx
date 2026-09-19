"use client";

import { MapPin } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { useAttendanceSettings } from "@/hooks/useAttendanceSettings";
import { usePermission } from "@/lib/staffAuth";
import { SectionHeader } from "./settings-ui";

/** Settings -> Attendance tab: the geofence (hospital location + allowed
 * radius), allowed Wi-Fi/IP ranges, and shift window (start/end, early
 * check-in, late threshold, optional auto-checkout) that /portal/check-in-
 * out validates every attempt against. Admin-only by default -- an
 * unlocked geofence radius would let anyone check in from anywhere, so
 * this is gated more strictly than the personal Attendance pages themselves. */
export function AttendanceSettingsTab() {
  const canView = usePermission("attendance_settings", "view");
  const canWrite = usePermission("attendance_settings", "write");
  const { settings, setSettings, saving, saved, error, handleSave } = useAttendanceSettings(canView);

  if (!canView) {
    return (
      <Card className="p-space-6">
        <p className="text-center text-[13px] text-ink-400">You don&apos;t have access to Attendance settings.</p>
      </Card>
    );
  }

  function useHere() {
    if (!settings || !navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        setSettings({
          ...settings,
          attendance_latitude: Math.round(pos.coords.latitude * 1e6) / 1e6,
          attendance_longitude: Math.round(pos.coords.longitude * 1e6) / 1e6,
        }),
      () => {},
    );
  }

  /** Appends the currently-detected IP to the existing comma-separated list
   * (rather than overwriting it) -- an admin may already have entries from
   * another location/ISP range and shouldn't lose them by clicking this. */
  function addDetectedIp() {
    if (!settings?.detected_ip) return;
    const existing = settings.attendance_allowed_ip_cidrs
      .split(",")
      .map((e) => e.trim())
      .filter(Boolean);
    if (existing.includes(settings.detected_ip)) return;
    setSettings({
      ...settings,
      attendance_allowed_ip_cidrs: [...existing, settings.detected_ip].join(", "),
    });
  }

  return (
    <form onSubmit={handleSave} className="flex flex-col gap-space-4">
      <Card className="p-space-4">
        <SectionHeader
          icon={MapPin}
          tint="brand"
          title="Hospital Location & Network"
          subtitle="Staff can only check in/out from this location or network -- leave blank to skip that check"
        />
        <p className="mb-space-3 text-[12.5px] text-ink-600">
          For the most reliable check-in, set up <span className="font-semibold">both</span> checks below --
          Location and Network. A check-in is accepted as long as it matches at least one of them, so if
          staff ever lose GPS signal indoors, the Network check still lets them in (and vice versa).
        </p>
        <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
          <Field label="Latitude" hint={!settings ? "Loading…" : undefined}>
            <Input
              type="number"
              step="any"
              placeholder="e.g. 25.6127"
              value={settings?.attendance_latitude ?? ""}
              onChange={(e) =>
                settings &&
                setSettings({ ...settings, attendance_latitude: e.target.value === "" ? null : Number(e.target.value) })
              }
              disabled={!settings || !canWrite}
            />
          </Field>
          <Field label="Longitude" hint={!settings ? "Loading…" : undefined}>
            <Input
              type="number"
              step="any"
              placeholder="e.g. 85.1421"
              value={settings?.attendance_longitude ?? ""}
              onChange={(e) =>
                settings &&
                setSettings({ ...settings, attendance_longitude: e.target.value === "" ? null : Number(e.target.value) })
              }
              disabled={!settings || !canWrite}
            />
          </Field>
        </div>
        <p className="mb-space-3 text-[12px] text-ink-500">
          <span className="font-semibold text-ink-700">Location check:</span> Latitude and Longitude are your
          hospital&apos;s exact map coordinates. When someone checks in, we compare their phone or laptop&apos;s
          GPS position against this point -- if they&apos;re within the Allowed Radius below, it passes. The
          easiest way to fill these in correctly: stand at the hospital and click the button below.
        </p>
        {canWrite && (
          <Button type="button" variant="secondary" onClick={useHere} disabled={!settings}>
            Use my current location
          </Button>
        )}
        <Field label="Allowed Radius" className="mt-space-3" hint="Distance (in meters) staff must be within to check in">
          <Input
            type="number"
            min={10}
            max={5000}
            value={settings?.attendance_allowed_radius_meters ?? 150}
            onChange={(e) => settings && setSettings({ ...settings, attendance_allowed_radius_meters: Number(e.target.value) })}
            disabled={!settings || !canWrite}
          />
        </Field>
        <Field
          label="Allowed Hospital IP / CIDR ranges"
          className="mb-0"
          hint="Comma-separated, e.g. 103.45.67.89, 103.45.68.0/24. Leave blank to skip this check."
        >
          <Textarea
            rows={2}
            value={settings?.attendance_allowed_ip_cidrs ?? ""}
            onChange={(e) => settings && setSettings({ ...settings, attendance_allowed_ip_cidrs: e.target.value })}
            disabled={!settings || !canWrite}
          />
        </Field>

        <div className="mt-space-3 rounded-md bg-brand-50 p-space-3 text-[12.5px] text-ink-700">
          <p className="font-bold text-ink-900">Network check: how to set this up</p>
          <p className="mt-space-1">
            While you&apos;re physically at the hospital, connected to its WiFi, open this page on your own
            phone or laptop. The box below shows the address your WiFi is using right now -- click
            &quot;Add this IP&quot; and save. You only need to do this <span className="font-semibold">once</span>:
            every staff member who later checks in from that same hospital WiFi will be recognized
            automatically, without any setup on their end.
          </p>
          <div className="mt-space-3 flex flex-wrap items-center gap-space-3 rounded-md border border-line bg-card p-space-3">
            <div className="min-w-0 flex-1">
              <p className="text-[11px] text-ink-400">This device&apos;s current network address</p>
              <p className="font-mono text-[13px] font-semibold text-ink-900">
                {settings?.detected_ip ?? (settings ? "Not available" : "Loading…")}
              </p>
            </div>
            {canWrite && settings?.detected_ip && (
              <Button type="button" variant="secondary" onClick={addDetectedIp}>
                Add this IP
              </Button>
            )}
          </div>
          <p className="mt-space-2 text-[11.5px] text-ink-400">
            Not at the hospital right now, or on a different network (home WiFi, mobile data)? The address
            shown above won&apos;t be the right one to add -- come back to this page once you&apos;re on
            the hospital&apos;s actual WiFi.
          </p>
        </div>
      </Card>

      <Card className="p-space-4">
        <SectionHeader
          icon={MapPin}
          tint="success"
          title="Shift Window"
          subtitle="When check-in opens, and when a check-in counts as late"
        />
        <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
          <Field label="Shift Start">
            <Input
              type="time"
              value={settings?.attendance_shift_start ?? ""}
              onChange={(e) => settings && setSettings({ ...settings, attendance_shift_start: e.target.value })}
              disabled={!settings || !canWrite}
            />
          </Field>
          <Field label="Shift End">
            <Input
              type="time"
              value={settings?.attendance_shift_end ?? ""}
              onChange={(e) => settings && setSettings({ ...settings, attendance_shift_end: e.target.value })}
              disabled={!settings || !canWrite}
            />
          </Field>
          <Field label="Early Check-in Window" hint="Minutes before shift start check-in opens">
            <Input
              type="number"
              min={0}
              max={240}
              value={settings?.attendance_early_checkin_minutes ?? 30}
              onChange={(e) => settings && setSettings({ ...settings, attendance_early_checkin_minutes: Number(e.target.value) })}
              disabled={!settings || !canWrite}
            />
          </Field>
          <Field label="Late Threshold" hint="Minutes after shift start before marked late">
            <Input
              type="number"
              min={0}
              max={240}
              value={settings?.attendance_late_threshold_minutes ?? 10}
              onChange={(e) => settings && setSettings({ ...settings, attendance_late_threshold_minutes: Number(e.target.value) })}
              disabled={!settings || !canWrite}
            />
          </Field>
          <Field
            label="Auto Checkout Grace Period"
            className="mb-0"
            hint="Optional -- minutes after each staff member's OWN shift ends before a forgotten check-out is auto-closed. Leave blank to turn this off."
          >
            <Input
              type="number"
              min={0}
              max={720}
              placeholder="Off"
              value={settings?.attendance_auto_checkout_grace_minutes ?? ""}
              onChange={(e) =>
                settings &&
                setSettings({
                  ...settings,
                  attendance_auto_checkout_grace_minutes: e.target.value === "" ? "" : Number(e.target.value),
                })
              }
              disabled={!settings || !canWrite}
            />
          </Field>
        </div>
        <p className="mt-space-3 text-[12px] text-ink-500">
          This uses each staff member&apos;s own shift hours (set on their profile) when they have one, and
          falls back to the Shift End above only for staff without their own hours configured -- so two staff
          on different shifts each get auto-checked-out at the right time for them, not one shared cutoff.
        </p>
      </Card>

      {canWrite && (
        <div className="flex flex-wrap items-center justify-end gap-space-2">
          {error && <p className="mr-auto text-[12.5px] font-medium text-error">{error}</p>}
          {saved && !error && <p className="mr-auto text-[12.5px] font-medium text-success">Saved.</p>}
          <Button type="submit" disabled={saving || !settings}>{saving ? "Saving…" : "Save Changes"}</Button>
        </div>
      )}
    </form>
  );
}
