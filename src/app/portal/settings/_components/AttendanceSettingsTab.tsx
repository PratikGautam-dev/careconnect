"use client";

import { useState } from "react";
import { MapPin } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { useAttendanceSettings } from "@/hooks/useAttendanceSettings";
import { validateAttendanceIpCidrs } from "@/lib/validation/attendanceIpCidrs";
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
  const { settings, setSettings, saving, saved, error, handleSave } =
    useAttendanceSettings(canView);
  const [cidrError, setCidrError] = useState<string | null>(null);

  if (!canView) {
    return (
      <Card className="p-space-6">
        <p className="text-ink-400 text-center text-[13px]">
          You don&apos;t have access to Attendance settings.
        </p>
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

  function handleSubmit(e: React.FormEvent) {
    const invalid = validateAttendanceIpCidrs(settings?.attendance_allowed_ip_cidrs ?? "");
    if (invalid) {
      e.preventDefault();
      setCidrError(invalid);
      return;
    }
    setCidrError(null);
    handleSave(e);
  }

  return (
    <form onSubmit={handleSubmit} className="gap-space-4 flex flex-col">
      <Card className="p-space-4">
        <SectionHeader
          icon={MapPin}
          tint="brand"
          title="Hospital Location & Network"
          subtitle="Staff can only check in/out from this location or network -- leave blank to skip that check"
        />
        <p className="mb-space-3 text-ink-600 text-[12.5px]">
          For the most reliable check-in, set up <span className="font-semibold">both</span> checks
          below -- Location and Network. A check-in is accepted as long as it matches at least one
          of them, so if staff ever lose GPS signal indoors, the Network check still lets them in
          (and vice versa).
        </p>
        <div className="gap-x-space-3 grid grid-cols-1 sm:grid-cols-2">
          <Field label="Latitude" hint={!settings ? "Loading…" : undefined}>
            <Input
              type="number"
              step="any"
              placeholder="e.g. 25.6127"
              value={settings?.attendance_latitude ?? ""}
              onChange={(e) =>
                settings &&
                setSettings({
                  ...settings,
                  attendance_latitude: e.target.value === "" ? null : Number(e.target.value),
                })
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
                setSettings({
                  ...settings,
                  attendance_longitude: e.target.value === "" ? null : Number(e.target.value),
                })
              }
              disabled={!settings || !canWrite}
            />
          </Field>
        </div>
        <p className="mb-space-3 text-ink-500 text-[12px]">
          <span className="text-ink-700 font-semibold">Location check:</span> Latitude and Longitude
          are your hospital&apos;s exact map coordinates. When someone checks in, we compare their
          phone or laptop&apos;s GPS position against this point -- if they&apos;re within the
          Allowed Radius below, it passes. The easiest way to fill these in correctly: stand at the
          hospital and click the button below.
        </p>
        {canWrite && (
          <Button type="button" variant="secondary" onClick={useHere} disabled={!settings}>
            Use my current location
          </Button>
        )}
        <Field
          label="Allowed Radius"
          className="mt-space-3"
          hint="Distance (in meters) staff must be within to check in"
        >
          <Input
            type="number"
            min={10}
            max={5000}
            value={settings?.attendance_allowed_radius_meters ?? 150}
            onChange={(e) =>
              settings &&
              setSettings({ ...settings, attendance_allowed_radius_meters: Number(e.target.value) })
            }
            disabled={!settings || !canWrite}
          />
        </Field>
        <Field
          label="Allowed Hospital IP / CIDR ranges"
          className="mb-0"
          error={cidrError || undefined}
          hint={
            cidrError
              ? undefined
              : "Comma-separated, e.g. 103.45.67.89, 103.45.68.0/24. Leave blank to skip this check."
          }
        >
          <Textarea
            rows={2}
            value={settings?.attendance_allowed_ip_cidrs ?? ""}
            invalid={!!cidrError}
            onChange={(e) => {
              setCidrError(null);
              if (settings)
                setSettings({ ...settings, attendance_allowed_ip_cidrs: e.target.value });
            }}
            disabled={!settings || !canWrite}
          />
        </Field>

        <div className="mt-space-3 bg-brand-50 p-space-3 text-ink-700 rounded-md text-[12.5px]">
          <p className="text-ink-900 font-bold">Network check: how to set this up</p>
          <p className="mt-space-1">
            While you&apos;re physically at the hospital, connected to its WiFi, open this page on
            your own phone or laptop. The box below shows the address your WiFi is using right now
            -- click &quot;Add this IP&quot; and save. You only need to do this{" "}
            <span className="font-semibold">once</span>: every staff member who later checks in from
            that same hospital WiFi will be recognized automatically, without any setup on their
            end.
          </p>
          <div className="mt-space-3 gap-space-3 border-line bg-card p-space-3 flex flex-wrap items-center rounded-md border">
            <div className="min-w-0 flex-1">
              <p className="text-ink-400 text-[11px]">This device&apos;s current network address</p>
              <p className="text-ink-900 font-mono text-[13px] font-semibold">
                {settings?.detected_ip ?? (settings ? "Not available" : "Loading…")}
              </p>
            </div>
            {canWrite && settings?.detected_ip && (
              <Button type="button" variant="secondary" onClick={addDetectedIp}>
                Add this IP
              </Button>
            )}
          </div>
          <p className="mt-space-2 text-ink-400 text-[11.5px]">
            Not at the hospital right now, or on a different network (home WiFi, mobile data)? The
            address shown above won&apos;t be the right one to add -- come back to this page once
            you&apos;re on the hospital&apos;s actual WiFi.
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
        <div className="gap-x-space-3 grid grid-cols-1 sm:grid-cols-2">
          <Field label="Shift Start">
            <Input
              type="time"
              value={settings?.attendance_shift_start ?? ""}
              onChange={(e) =>
                settings && setSettings({ ...settings, attendance_shift_start: e.target.value })
              }
              disabled={!settings || !canWrite}
            />
          </Field>
          <Field label="Shift End">
            <Input
              type="time"
              value={settings?.attendance_shift_end ?? ""}
              onChange={(e) =>
                settings && setSettings({ ...settings, attendance_shift_end: e.target.value })
              }
              disabled={!settings || !canWrite}
            />
          </Field>
          <Field label="Early Check-in Window" hint="Minutes before shift start check-in opens">
            <Input
              type="number"
              min={0}
              max={240}
              value={settings?.attendance_early_checkin_minutes ?? 30}
              onChange={(e) =>
                settings &&
                setSettings({
                  ...settings,
                  attendance_early_checkin_minutes: Number(e.target.value),
                })
              }
              disabled={!settings || !canWrite}
            />
          </Field>
          <Field label="Late Threshold" hint="Minutes after shift start before marked late">
            <Input
              type="number"
              min={0}
              max={240}
              value={settings?.attendance_late_threshold_minutes ?? 10}
              onChange={(e) =>
                settings &&
                setSettings({
                  ...settings,
                  attendance_late_threshold_minutes: Number(e.target.value),
                })
              }
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
                  attendance_auto_checkout_grace_minutes:
                    e.target.value === "" ? "" : Number(e.target.value),
                })
              }
              disabled={!settings || !canWrite}
            />
          </Field>
        </div>
        <p className="mt-space-3 text-ink-500 text-[12px]">
          This uses each staff member&apos;s own shift hours (set on their profile) when they have
          one, and falls back to the Shift End above only for staff without their own hours
          configured -- so two staff on different shifts each get auto-checked-out at the right time
          for them, not one shared cutoff.
        </p>
      </Card>

      {canWrite && (
        <div className="gap-space-2 flex flex-wrap items-center justify-end">
          {error && <p className="text-error mr-auto text-[12.5px] font-medium">{error}</p>}
          {saved && !error && (
            <p className="text-success mr-auto text-[12.5px] font-medium">Saved.</p>
          )}
          <Button type="submit" disabled={saving || !settings}>
            {saving ? "Saving…" : "Save Changes"}
          </Button>
        </div>
      )}
    </form>
  );
}
