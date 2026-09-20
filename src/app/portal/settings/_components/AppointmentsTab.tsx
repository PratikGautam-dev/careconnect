"use client";

import { useState } from "react";
import { Banknote, CalendarDays, FlaskConical, ListChecks, MapPin } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { AppointmentTypeToggles } from "@/components/portal/AppointmentTypeToggles";
import { DiagnosticTestsManager } from "@/components/portal/DiagnosticTestsManager";
import { LabServiceAreasManager } from "@/components/portal/LabServiceAreasManager";
import { usePortalSettings } from "@/hooks/usePortalSettings";
import type { PortalHospital } from "@/lib/portalAuth";
import {
  ADVANCE_BOOKING_DAYS_OPTIONS,
  BUFFER_MINUTES_OPTIONS,
  DURATION_MINUTES_OPTIONS,
} from "./general-settings-mock";
import { NumberSelect, SectionHeader, ToggleRow, withValue } from "./settings-ui";

/** Appointments tab of /portal/settings -- split out of General (which had
 * grown five appointment-related sections crammed in alongside Hospital
 * Information/Contact/Security, confirmed messy with the user). Everything
 * here is real, backend-wired: Appointment Settings and Follow-up & Fees
 * via usePortalSettings (this tab's own instance, same pattern
 * NotificationsTab/GeneralSettingsTab each use their own), Appointment
 * Types/Diagnostic Tests/Lab Service Areas each their own independent
 * manager gated by the relevant admin_capabilities. No local mock state at
 * all -- unlike General, there's nothing here for a "Reset to Default"
 * button to reset, so this tab only has Save Changes. */
export function AppointmentsTab({ hospital }: { hospital: PortalHospital | null }) {
  // !hospital means "still loading", not "no capabilities".
  const canManageAppointmentTypes =
    !hospital || hospital.admin_capabilities?.includes("manage_appointment_types");
  const canManageTests =
    !hospital || hospital.admin_capabilities?.includes("manage_diagnostic_resources");

  // `true` here (not a `ready` prop) is safe: AppointmentsTab only ever
  // mounts once PortalSettingsPage's own usePortalGuard is already ready.
  const {
    settings: portalSettings,
    setSettings: setPortalSettings,
    saving,
    saved,
    error,
    handleSave,
  } = usePortalSettings(true);
  const [dateError, setDateError] = useState<string | null>(null);

  // "Closed until" before "Closed from" would silently mean an empty/
  // inverted closure window server-side -- same from/to ordering check
  // NewLeaveRequestDialog already does for its own date pair, just gated
  // here in front of usePortalSettings' own handleSave (which has no
  // validation hook of its own) instead of inside it.
  function handleSubmit(e: React.FormEvent) {
    if (
      portalSettings?.booking_closure_from_date &&
      portalSettings.booking_closure_to_date &&
      portalSettings.booking_closure_to_date < portalSettings.booking_closure_from_date
    ) {
      e.preventDefault();
      setDateError('"Closed until" must be on or after "Closed from".');
      return;
    }
    setDateError(null);
    handleSave(e);
  }

  return (
    <div className="gap-space-4 flex flex-col">
      <form onSubmit={handleSubmit} className="gap-space-4 flex flex-col">
        <Card className="p-space-4">
          <SectionHeader
            icon={CalendarDays}
            tint="brand"
            title="Appointment Settings"
            subtitle="Configure appointment related preferences"
          />
          <div className="gap-x-space-3 grid grid-cols-1 sm:grid-cols-2">
            <Field
              label="Default Appointment Duration"
              hint={
                !portalSettings
                  ? "Loading…"
                  : "Used for any doctor who hasn't set their own slot length"
              }
            >
              <NumberSelect
                value={portalSettings?.default_appointment_duration_minutes ?? 30}
                onChange={(v) =>
                  portalSettings &&
                  setPortalSettings({
                    ...portalSettings,
                    default_appointment_duration_minutes: v,
                  })
                }
                options={withValue(
                  DURATION_MINUTES_OPTIONS,
                  portalSettings?.default_appointment_duration_minutes ?? 30,
                )}
                suffix="minutes"
                disabled={!portalSettings}
              />
            </Field>
            <Field
              label="Buffer Time Between Appointments"
              hint={
                !portalSettings
                  ? "Loading…"
                  : "Gap kept free between every doctor's back-to-back slots"
              }
            >
              <NumberSelect
                value={portalSettings?.buffer_minutes ?? 0}
                onChange={(v) =>
                  portalSettings && setPortalSettings({ ...portalSettings, buffer_minutes: v })
                }
                options={withValue(BUFFER_MINUTES_OPTIONS, portalSettings?.buffer_minutes ?? 0)}
                suffix="minutes"
                disabled={!portalSettings}
              />
            </Field>
            <Field label="Advance Booking Limit" hint={!portalSettings ? "Loading…" : undefined}>
              <NumberSelect
                value={portalSettings?.future_booking_days ?? 90}
                onChange={(v) =>
                  portalSettings && setPortalSettings({ ...portalSettings, future_booking_days: v })
                }
                options={withValue(
                  ADVANCE_BOOKING_DAYS_OPTIONS,
                  portalSettings?.future_booking_days ?? 90,
                )}
                suffix="days"
                disabled={!portalSettings}
              />
            </Field>
            <Field
              label="Maximum Appointments Per Day"
              hint={!portalSettings ? "Loading…" : "Leave blank for no daily cap"}
            >
              <Input
                type="number"
                min={1}
                placeholder="No limit"
                value={portalSettings?.max_appointments_per_day ?? ""}
                onChange={(e) =>
                  portalSettings &&
                  setPortalSettings({
                    ...portalSettings,
                    max_appointments_per_day: e.target.value === "" ? "" : Number(e.target.value),
                  })
                }
                disabled={!portalSettings}
              />
            </Field>
          </div>
          {portalSettings && portalSettings.max_appointments_per_day !== "" && (
            <div className="mt-space-2">
              <div className="mb-space-1 text-ink-400 flex items-center justify-between text-[12px]">
                <span>Booked today</span>
                <span className="text-ink-700 font-semibold">
                  {portalSettings.appointments_today_count} out of{" "}
                  {portalSettings.max_appointments_per_day}
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-black/6">
                <div
                  className="bg-brand-600 h-full rounded-full"
                  style={{
                    width: `${Math.min(
                      100,
                      (portalSettings.appointments_today_count /
                        (portalSettings.max_appointments_per_day || 1)) *
                        100,
                    )}%`,
                  }}
                />
              </div>
            </div>
          )}
          <div className="mt-space-2">
            <ToggleRow
              label="Allow Online Appointments"
              subtitle="Patients can self-book via WhatsApp"
              checked={portalSettings?.allow_online_appointments ?? true}
              disabled={!portalSettings}
              onChange={() =>
                portalSettings &&
                setPortalSettings({
                  ...portalSettings,
                  allow_online_appointments: !portalSettings.allow_online_appointments,
                })
              }
            />
            {portalSettings && (
              <div className="mt-space-3 gap-space-3 border-line p-space-3 rounded-md border">
                <div className="gap-space-3 grid grid-cols-1 sm:grid-cols-2">
                  <Field label="Closed from" htmlFor="booking_closure_from_date" className="mb-0">
                    <Input
                      id="booking_closure_from_date"
                      type="date"
                      value={portalSettings.booking_closure_from_date}
                      invalid={!!dateError}
                      onChange={(e) => {
                        setDateError(null);
                        setPortalSettings({
                          ...portalSettings,
                          booking_closure_from_date: e.target.value,
                        });
                      }}
                    />
                  </Field>
                  <Field
                    label="Closed until"
                    htmlFor="booking_closure_to_date"
                    className="mb-0"
                    error={dateError || undefined}
                  >
                    <Input
                      id="booking_closure_to_date"
                      type="date"
                      value={portalSettings.booking_closure_to_date}
                      invalid={!!dateError}
                      onChange={(e) => {
                        setDateError(null);
                        setPortalSettings({
                          ...portalSettings,
                          booking_closure_to_date: e.target.value,
                        });
                      }}
                    />
                  </Field>
                </div>
                <Field
                  label="Message shown to patients"
                  htmlFor="closing_message_text"
                  className="mt-space-3 mb-0"
                  hint='Only takes effect while "Allow Online Appointments" above is off, and today falls between the dates set here. Sent instead of the main menu, e.g. "The hospital is closed and will reopen on 25 Oct."'
                >
                  <Textarea
                    id="closing_message_text"
                    rows={2}
                    value={portalSettings.closing_message_text}
                    onChange={(e) =>
                      setPortalSettings({ ...portalSettings, closing_message_text: e.target.value })
                    }
                  />
                </Field>
              </div>
            )}
          </div>
        </Card>

        <Card className="p-space-4">
          <SectionHeader
            icon={Banknote}
            tint="success"
            title="Follow-up & Fees"
            subtitle="How long a Follow-up stays bookable after a visit, and the fees shown on booking confirmations"
          />
          <p className="mb-space-3 text-ink-400 text-[12.5px]">
            Leave a fee blank to omit that line entirely from the confirmation message, rather than
            showing ₹0.
          </p>
          <div className="gap-x-space-3 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4">
            <Field
              label="Follow-up Eligibility Window"
              hint={
                !portalSettings
                  ? "Loading…"
                  : "Days after the visit a Follow-up can still be booked"
              }
            >
              <Input
                type="number"
                min={1}
                max={365}
                value={portalSettings?.followup_validity_days ?? 30}
                onChange={(e) =>
                  portalSettings &&
                  setPortalSettings({
                    ...portalSettings,
                    followup_validity_days: Number(e.target.value),
                  })
                }
                disabled={!portalSettings}
              />
            </Field>
            <Field
              label="Follow-up Fee (₹)"
              hint={!portalSettings ? "Loading…" : "Blank = no fee line shown"}
            >
              <Input
                type="number"
                min={0}
                placeholder="No fee"
                value={portalSettings?.followup_fee ?? ""}
                onChange={(e) =>
                  portalSettings &&
                  setPortalSettings({
                    ...portalSettings,
                    followup_fee: e.target.value === "" ? "" : Number(e.target.value),
                  })
                }
                disabled={!portalSettings}
              />
            </Field>
            <Field
              label="New Consultation Fee (₹)"
              hint={!portalSettings ? "Loading…" : "Not shown to patients yet"}
            >
              <Input
                type="number"
                min={0}
                placeholder="No fee"
                value={portalSettings?.new_consultation_fee ?? ""}
                onChange={(e) =>
                  portalSettings &&
                  setPortalSettings({
                    ...portalSettings,
                    new_consultation_fee: e.target.value === "" ? "" : Number(e.target.value),
                  })
                }
                disabled={!portalSettings}
              />
            </Field>
            <Field
              label="Home Sample Collection Charge (₹)"
              hint={
                !portalSettings ? "Loading…" : "Added for home sample collection Lab Test bookings"
              }
              className="mb-0"
            >
              <Input
                type="number"
                min={0}
                placeholder="No charge"
                value={portalSettings?.home_collection_charge ?? ""}
                onChange={(e) =>
                  portalSettings &&
                  setPortalSettings({
                    ...portalSettings,
                    home_collection_charge: e.target.value === "" ? "" : Number(e.target.value),
                  })
                }
                disabled={!portalSettings}
              />
            </Field>
          </div>
        </Card>

        <div className="gap-space-2 flex flex-wrap items-center justify-end">
          {error && <p className="text-error mr-auto text-[12.5px] font-medium">{error}</p>}
          {saved && !error && (
            <p className="text-success mr-auto text-[12.5px] font-medium">Saved.</p>
          )}
          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save Changes"}
          </Button>
        </div>
      </form>

      {/* The sections below are each their own independent, real, already-
        wired manager -- deliberately OUTSIDE the form above (nested <form>s
        are invalid HTML and break hydration) and not tied to its Save button. */}
      {canManageAppointmentTypes && (
        <Card className="p-space-4">
          <SectionHeader
            icon={ListChecks}
            tint="brand"
            title="Appointment Types"
            subtitle="Which booking types patients can choose -- separate from the general appointment settings above"
          />
          <p className="mb-space-3 text-ink-400 text-[12.5px]">
            The card above (&quot;Appointment Settings&quot;) controls HOW appointments behave --
            duration, buffer time, approval (reminders are on the Notifications tab). This one
            controls WHICH appointment types show up at all in the WhatsApp booking menu (e.g.
            Doctor Consultation, Daycare, Diagnostic Test). Turn a type off here and patients simply
            won&apos;t see it as an option. A type greyed out below hasn&apos;t been enabled for
            your account by the platform -- contact support to request it.
          </p>
          <AppointmentTypeToggles canManage={!!canManageAppointmentTypes} />
        </Card>
      )}

      <Card className="p-space-4">
        <SectionHeader
          icon={FlaskConical}
          tint="success"
          title="Diagnostic Tests"
          subtitle="Manage the tests patients can book under Diagnostic Test / Lab Test, each with its own weekly schedule"
        />
        <DiagnosticTestsManager canManage={!!canManageTests} />
      </Card>

      {canManageAppointmentTypes && (
        <Card className="p-space-4">
          <SectionHeader
            icon={MapPin}
            tint="error"
            title="Lab Service Areas"
            subtitle="PIN codes where you offer Home Sample Collection for Lab Test bookings"
          />
          <p className="mb-space-3 text-ink-400 text-[12.5px]">
            A patient entering a PIN code not listed here is offered Visit Hospital/Lab instead of
            Home Collection.
          </p>
          <LabServiceAreasManager canManage={!!canManageAppointmentTypes} />
        </Card>
      )}
    </div>
  );
}
