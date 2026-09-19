"use client";

import { useState } from "react";
import { Bell, MessageSquareText } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { usePortalSettings } from "@/hooks/usePortalSettings";
import { toast } from "@/lib/toast";
import { initialGeneralSettings, type NotificationPreferencesMock } from "./general-settings-mock";
import { SectionHeader, ToggleRow } from "./settings-ui";

/** Notifications tab -- two cards. "Notification Preferences" is a
 * frontend-only mock toggle set. "Message Templates & Content" is real,
 * wired to usePortalSettings: what patients actually see in a WhatsApp
 * message (welcome text, reminder copy/timing, closing message) --
 * distinct from Preferences' on/off switches, this is the message CONTENT
 * itself. There's no way to customize the consent notice text; every
 * hospital gets the generic default. */
export function NotificationsTab() {
  const [notifications, setNotifications] = useState<NotificationPreferencesMock>(
    initialGeneralSettings().notifications,
  );

  // `true` here (not a `ready` prop) is safe: this tab only ever mounts once
  // PortalSettingsPage's own usePortalGuard is already ready.
  const { settings, setSettings, saving, saved, error, handleSave } = usePortalSettings(true);

  function patchNotification(key: keyof NotificationPreferencesMock) {
    setNotifications((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function handleResetPreferences() {
    setNotifications(initialGeneralSettings().notifications);
    toast.success("Reset to default", "Notification preferences reverted to their defaults.");
  }

  return (
    <div className="gap-space-4 flex flex-col">
      <Card className="p-space-4">
        <SectionHeader
          icon={Bell}
          tint="clay"
          title="Notification Preferences"
          subtitle="Choose how and when to send notifications"
        />
        <div className="divide-line divide-y">
          <ToggleRow
            label="Appointment Confirmations"
            subtitle="Notify patients when appointment is confirmed"
            checked={notifications.appointmentConfirmations}
            onChange={() => patchNotification("appointmentConfirmations")}
          />
          <ToggleRow
            label="Appointment Reminders"
            subtitle="Send reminder before appointment"
            checked={notifications.appointmentReminders}
            onChange={() => patchNotification("appointmentReminders")}
          />
          <ToggleRow
            label="Follow-up Reminders"
            subtitle="Notify for follow-up appointments"
            checked={notifications.followUpReminders}
            onChange={() => patchNotification("followUpReminders")}
          />
          <ToggleRow
            label="Lab Report Notifications"
            subtitle="Notify when lab reports are ready"
            checked={notifications.labReportNotifications}
            onChange={() => patchNotification("labReportNotifications")}
          />
          <ToggleRow
            label="System Announcements"
            subtitle="Important updates and maintenance"
            checked={notifications.systemAnnouncements}
            onChange={() => patchNotification("systemAnnouncements")}
          />
          <ToggleRow
            label="Marketing Communications"
            subtitle="Send health tips and newsletters"
            checked={notifications.marketingCommunications}
            onChange={() => patchNotification("marketingCommunications")}
          />
        </div>
        <div className="mt-space-3 flex justify-end">
          <Button type="button" variant="secondary" size="md" onClick={handleResetPreferences}>
            Reset to Default
          </Button>
        </div>
      </Card>

      <form onSubmit={handleSave}>
        <Card className="p-space-4">
          <SectionHeader
            icon={MessageSquareText}
            tint="brand"
            title="Message Templates & Content"
            subtitle="What patients actually see in a WhatsApp message"
          />
          {!settings ? (
            <p className="text-ink-400 text-[13px]">Loading…</p>
          ) : (
            <>
              <Field
                label="Welcome message"
                htmlFor="welcome_message_text"
                hint="Shown when a patient's conversation starts. Leave blank to show a default greeting with your hospital's name."
              >
                <Textarea
                  id="welcome_message_text"
                  rows={2}
                  value={settings.welcome_message_text}
                  onChange={(e) =>
                    setSettings({ ...settings, welcome_message_text: e.target.value })
                  }
                />
              </Field>
              <div className="gap-x-space-3 grid grid-cols-1 sm:grid-cols-2">
                <Field
                  label="Reminder offsets (comma-separated hours)"
                  htmlFor="reminder_offsets_hours"
                  hint="How many hours before the appointment a WhatsApp reminder goes out. e.g. 24,1 sends one a day before and one an hour before."
                >
                  <Input
                    id="reminder_offsets_hours"
                    value={settings.reminder_offsets_hours}
                    onChange={(e) =>
                      setSettings({ ...settings, reminder_offsets_hours: e.target.value })
                    }
                  />
                </Field>
                <Field label="Reminder template name" htmlFor="reminder_template_name">
                  <Input
                    id="reminder_template_name"
                    value={settings.reminder_template_name}
                    onChange={(e) =>
                      setSettings({ ...settings, reminder_template_name: e.target.value })
                    }
                  />
                </Field>
              </div>
              <Field
                label="Closing / thank-you message"
                htmlFor="closing_message_text"
                className="mb-0"
                hint='Appended after a booking/cancellation/reschedule completes, e.g. "Thank you for choosing City Hospital. For emergencies, call 102."'
              >
                <Textarea
                  id="closing_message_text"
                  rows={2}
                  value={settings.closing_message_text}
                  onChange={(e) =>
                    setSettings({ ...settings, closing_message_text: e.target.value })
                  }
                />
              </Field>
            </>
          )}
          <div className="mt-space-3 gap-space-2 flex flex-wrap items-center justify-end">
            {error && <p className="text-error mr-auto text-[12.5px] font-medium">{error}</p>}
            {saved && !error && (
              <p className="text-success mr-auto text-[12.5px] font-medium">Saved.</p>
            )}
            <Button type="submit" disabled={saving || !settings}>
              {saving ? "Saving…" : "Save Changes"}
            </Button>
          </div>
        </Card>
      </form>
    </div>
  );
}
