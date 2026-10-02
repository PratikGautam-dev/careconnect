"use client";

import { useState } from "react";
import { AlertTriangle, Lightbulb, MapPin, Wifi } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { useAttendanceSettings } from "@/hooks/useAttendanceSettings";
import { validateAttendanceIpCidrs } from "@/lib/validation/attendanceIpCidrs";
import { usePermission } from "@/lib/staffAuth";
import { SectionHeader } from "./settings-ui";

const MIN_RADIUS_METERS = 50;
const MAX_RADIUS_METERS = 5000;
const RADIUS_SUGGESTIONS = [100, 200, 300];

/** Settings -> Attendance tab: the hospital location + allowed distance, the
 * optional WiFi (IP) check, and the shift window (start/end, early check-in,
 * late threshold, optional auto-checkout) that /portal/check-in-out
 * validates every attempt against. Written for a hospital admin, not an IT
 * person -- no "geofence"/"CIDR" on screen. Admin-only by default -- an
 * unlocked radius would let anyone check in from anywhere, so this is gated
 * more strictly than the personal Attendance pages themselves. */
export function AttendanceSettingsTab() {
  const canView = usePermission("attendance_settings", "view");
  const canWrite = usePermission("attendance_settings", "write");
  const { settings, setSettings, saving, saved, error, handleSave } =
    useAttendanceSettings(canView);
  const [cidrError, setCidrError] = useState<string | null>(null);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [locationWarning, setLocationWarning] = useState<string | null>(null);
  const [radiusError, setRadiusError] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);

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
    if (!settings) return;
    if (!navigator.geolocation) {
      setLocationError("This device can't share its location. Type the coordinates in instead.");
      return;
    }
    setLocating(true);
    setLocationError(null);
    setLocationWarning(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        setSettings({
          ...settings,
          attendance_latitude: Math.round(pos.coords.latitude * 1e6) / 1e6,
          attendance_longitude: Math.round(pos.coords.longitude * 1e6) / 1e6,
        });
        if (pos.coords.accuracy > 100) {
          setLocationWarning(
            `This reading may be off by about ${Math.round(pos.coords.accuracy)} m. For an exact spot, open this page on your phone while standing at the hospital entrance and try again.`,
          );
        }
      },
      () => {
        setLocating(false);
        setLocationError(
          "We couldn't get your location. Allow location access for this site in your browser, or type the coordinates in.",
        );
      },
      { enableHighAccuracy: true, timeout: 15_000 },
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
    setCidrError(null);
    setSettings({
      ...settings,
      attendance_allowed_ip_cidrs: [...existing, settings.detected_ip].join(", "),
    });
  }

  function handleSubmit(e: React.FormEvent) {
    if (!settings) return;
    let invalid = false;
    const hasLat = settings.attendance_latitude !== null;
    const hasLng = settings.attendance_longitude !== null;

    setLocationError(null);
    if (hasLat !== hasLng) {
      setLocationError(
        "Enter both latitude and longitude, or clear both to turn the location check off.",
      );
      invalid = true;
    }
    setRadiusError(null);
    if (hasLat && hasLng) {
      const radius = settings.attendance_allowed_radius_meters;
      if (radius === "" || Number.isNaN(Number(radius))) {
        setRadiusError(
          "Enter how far from the hospital staff may check in, in meters (for example 200).",
        );
        invalid = true;
      } else if (Number(radius) < MIN_RADIUS_METERS || Number(radius) > MAX_RADIUS_METERS) {
        setRadiusError(
          `Enter a distance between ${MIN_RADIUS_METERS} and ${MAX_RADIUS_METERS} meters.`,
        );
        invalid = true;
      }
    }
    setCidrError(null);
    if (settings.attendance_ip_check_enabled) {
      const text = settings.attendance_allowed_ip_cidrs.trim();
      const badEntry = validateAttendanceIpCidrs(text);
      if (!text) {
        setCidrError("Add your hospital WiFi's network address, or switch the WiFi check off.");
        invalid = true;
      } else if (badEntry) {
        setCidrError(badEntry);
        invalid = true;
      }
    }
    if (invalid) {
      e.preventDefault();
      return;
    }
    handleSave(e);
  }

  const locationOn =
    settings?.attendance_latitude != null && settings?.attendance_longitude != null;
  const wifiOn = !!settings?.attendance_ip_check_enabled;

  return (
    <form onSubmit={handleSubmit} className="gap-space-4 flex flex-col">
      <Card className="p-space-4">
        <SectionHeader
          icon={MapPin}
          tint="brand"
          title="1. Hospital location"
          subtitle="Staff can check in when their phone shows they are at the hospital"
        />
        <p className="mb-space-3 text-ink-600 text-[12.5px]">
          Tell us where your hospital is and how far from that spot staff may check in. When someone
          taps Check In, we compare their phone&apos;s location with this spot. This works without
          WiFi, so staff can still check in if your internet is down.
        </p>
        <div className="gap-x-space-3 grid grid-cols-1 sm:grid-cols-2">
          <Field label="Latitude" hint={!settings ? "Loading…" : undefined}>
            <Input
              type="number"
              step="any"
              placeholder="e.g. 25.6127"
              value={settings?.attendance_latitude ?? ""}
              onChange={(e) => {
                setLocationError(null);
                setLocationWarning(null);
                if (settings)
                  setSettings({
                    ...settings,
                    attendance_latitude: e.target.value === "" ? null : Number(e.target.value),
                  });
              }}
              disabled={!settings || !canWrite}
            />
          </Field>
          <Field label="Longitude" hint={!settings ? "Loading…" : undefined}>
            <Input
              type="number"
              step="any"
              placeholder="e.g. 85.1421"
              value={settings?.attendance_longitude ?? ""}
              onChange={(e) => {
                setLocationError(null);
                setLocationWarning(null);
                if (settings)
                  setSettings({
                    ...settings,
                    attendance_longitude: e.target.value === "" ? null : Number(e.target.value),
                  });
              }}
              disabled={!settings || !canWrite}
            />
          </Field>
        </div>
        {canWrite && (
          <>
            <Button
              type="button"
              variant="secondary"
              onClick={useHere}
              disabled={!settings || locating}
            >
              {locating ? "Finding your location…" : "Use my current location"}
            </Button>
            <div className="mt-space-2 gap-space-2 border-brand-100 bg-brand-50 p-space-3 text-ink-700 flex items-start rounded-md border text-[12.5px]">
              <Lightbulb size={15} strokeWidth={2} className="text-brand-600 mt-0.5 shrink-0" />
              <p>
                <span className="text-ink-900 font-bold">Tip:</span> open this page{" "}
                <span className="font-semibold">on your phone</span> while standing at the hospital
                entrance, then tap the button. A phone is far more accurate than a laptop.
              </p>
            </div>
          </>
        )}
        {locationError && (
          <p className="mt-space-2 text-error text-[12.5px] font-medium">{locationError}</p>
        )}
        {locationWarning && (
          <div className="mt-space-2 gap-space-2 border-clay-300 bg-clay-100 p-space-3 text-clay-700 flex items-start rounded-md border text-[12.5px]">
            <AlertTriangle size={15} strokeWidth={2} className="text-clay-500 mt-0.5 shrink-0" />
            <p>{locationWarning}</p>
          </div>
        )}

        <Field
          label="Allowed distance (meters)"
          required={locationOn}
          className="mt-space-4"
          error={radiusError || undefined}
          hint={
            radiusError
              ? undefined
              : "How far from the spot above staff may be and still check in. We suggest 150-300 m for a hospital building -- phones can be off by tens of meters indoors, so a very small distance will turn away staff who are really at work."
          }
        >
          <Input
            type="number"
            min={MIN_RADIUS_METERS}
            max={MAX_RADIUS_METERS}
            placeholder="e.g. 200"
            value={settings?.attendance_allowed_radius_meters ?? ""}
            invalid={!!radiusError}
            onChange={(e) => {
              setRadiusError(null);
              if (settings)
                setSettings({
                  ...settings,
                  attendance_allowed_radius_meters:
                    e.target.value === "" ? "" : Number(e.target.value),
                });
            }}
            disabled={!settings || !canWrite}
          />
        </Field>
        {canWrite && (
          <div className="gap-space-2 -mt-space-2 flex flex-wrap items-center">
            <span className="text-hint">Quick pick:</span>
            {RADIUS_SUGGESTIONS.map((m) => (
              <button
                key={m}
                type="button"
                disabled={!settings}
                onClick={() => {
                  setRadiusError(null);
                  if (settings) setSettings({ ...settings, attendance_allowed_radius_meters: m });
                }}
                className="border-line text-ink-600 hover:border-brand-300 hover:bg-brand-50 px-space-2 h-7 rounded-md border text-[12px] font-semibold"
              >
                {m} m
              </button>
            ))}
          </div>
        )}
        <p className="mt-space-3 text-hint">
          Leave latitude and longitude empty to turn the location check off.
        </p>
      </Card>

      <Card className="p-space-4">
        <div className="mb-space-3 gap-space-3 flex items-start justify-between">
          <div className="gap-space-3 flex items-start">
            <span className="bg-success-tint text-success flex h-9 w-9 shrink-0 items-center justify-center rounded-md">
              <Wifi size={17} strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <h3 className="text-ink-900 text-[14px] font-bold">2. Hospital WiFi check</h3>
              <p className="text-hint">
                Optional extra proof that staff are really inside the hospital
              </p>
            </div>
          </div>
          <Switch
            checked={wifiOn}
            disabled={!settings || !canWrite}
            aria-label="Check staff are on the hospital WiFi"
            onChange={() => {
              setCidrError(null);
              if (settings)
                setSettings({
                  ...settings,
                  attendance_ip_check_enabled: !settings.attendance_ip_check_enabled,
                });
            }}
          />
        </div>
        <p className="mb-space-3 text-ink-600 text-[12.5px]">
          {wifiOn
            ? "On: a staff member connected to your hospital WiFi is checked in automatically and marked as verified by WiFi. Someone checking in by location only (for example on mobile data) is still allowed, but is flagged so you can review it on the Attendance Overview page."
            : "Off: staff are checked in by location only. Turn this on to also confirm they are on the hospital WiFi."}
        </p>

        {wifiOn && (
          <>
            <Field
              label="Hospital WiFi network address"
              required
              className="mb-0"
              error={cidrError || undefined}
              hint={
                cidrError
                  ? undefined
                  : "The public internet address of your hospital WiFi, e.g. 103.45.67.89. Add more than one, separated by commas, if you have several connections."
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
              <p className="text-ink-900 font-bold">How to fill this in</p>
              <p className="mt-space-1">
                While you&apos;re at the hospital, connected to its WiFi, open this page on your
                phone or laptop. The address below is the one your WiFi is using right now -- tap
                &quot;Add this address&quot; and save. You only do this once; every staff member on
                that WiFi is recognized automatically.
              </p>
              <div className="mt-space-3 gap-space-3 border-line bg-card p-space-3 flex flex-wrap items-center rounded-md border">
                <div className="min-w-0 flex-1">
                  <p className="text-ink-400 text-[11px]">
                    This device&apos;s current WiFi address
                  </p>
                  <p className="text-ink-900 font-mono text-[13px] font-semibold">
                    {settings?.detected_ip ?? (settings ? "Not available" : "Loading…")}
                  </p>
                </div>
                {canWrite && settings?.detected_ip && (
                  <Button type="button" variant="secondary" onClick={addDetectedIp}>
                    Add this address
                  </Button>
                )}
              </div>
              <p className="mt-space-2 text-ink-500 text-[11.5px]">
                Not at the hospital, or on home WiFi or mobile data? The address above won&apos;t be
                the right one -- come back once you&apos;re on the hospital&apos;s own WiFi. Tip:
                ask your internet provider for a &quot;static IP&quot; so this address never
                changes; otherwise you may need to update it when it does.
              </p>
            </div>
          </>
        )}
      </Card>

      {settings && !locationOn && !wifiOn && (
        <div className="gap-space-2 border-clay-300 bg-clay-100 p-space-3 text-clay-700 flex items-start rounded-md border text-[12.5px]">
          <AlertTriangle size={16} strokeWidth={2} className="text-clay-500 mt-0.5 shrink-0" />
          <p>
            <span className="font-bold">Check-in isn&apos;t being verified.</span> Neither the
            location check nor the WiFi check is on, so anyone can check in from anywhere. Set the
            hospital location above (recommended) or turn the WiFi check on.
          </p>
        </div>
      )}

      <Card className="p-space-4">
        <SectionHeader
          icon={MapPin}
          tint="success"
          title="3. Shift window"
          subtitle="When check-in opens, and when a check-in counts as late"
        />
        <div className="gap-x-space-3 grid grid-cols-1 sm:grid-cols-2">
          {/* Hospital-wide Shift Start/End are hidden: every staff member and
              doctor has their own shift hours on their profile, which is
              what late/auto-checkout use. The saved values (empty for most)
              are still sent back untouched on save. */}
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
          This uses each staff member&apos;s own shift hours (set on their profile), so two staff on
          different shifts each get auto-checked-out at the right time for them, not one shared
          cutoff.
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
