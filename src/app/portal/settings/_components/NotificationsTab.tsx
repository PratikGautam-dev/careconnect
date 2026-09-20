"use client";

import { useState } from "react";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { usePortalSettings } from "@/hooks/usePortalSettings";
import { validateReminderOffsetsHours } from "@/lib/validation/reminderOffsets";
import { toast } from "@/lib/toast";
import { initialGeneralSettings, type NotificationPreferencesMock } from "./general-settings-mock";
import { SectionHeader, ToggleRow } from "./settings-ui";

/** Notifications tab -- one card, "Notification Preferences". Mostly a
 * frontend-only mock toggle set, EXCEPT the "Appointment Reminders" group
 * (top of the list) -- that one is real, wired to usePortalSettings'
 * reminders_enabled/reminder_offsets_hours/reminder_template_name.
 * (Appointment/Follow-up Reminders used to be two separate mock toggles
 * here, both describing the same thing -- merged into this one real toggle
 * instead, since reminders/scheduler.py's send_reminders() already reaches
 * every upcoming appointment with no type filter.) The Save Changes button
 * below exists solely to persist this real toggle/its offsets/template --
 * everything else on this tab is frontend-only mock state, reset by its own
 * "Reset to Default" button rather than persisted.
 *
 * There used to be a second card here, "Message Templates & Content"
 * (the Welcome message field) -- moved to General Settings' "Hospital
 * Information" card instead, since it's hospital-identity content, not a
 * notification setting (confirmed with the user). "Closing / thank-you
 * message" moved to General Settings' "Allow Online Appointments" toggle
 * even earlier, since closing_message_text is now the "online booking
 * closed" notice rather than a generic post-booking append -- so this tab
 * no longer owns any message-content fields at all. */
export function NotificationsTab() {
  const [notifications, setNotifications] = useState<NotificationPreferencesMock>(
    initialGeneralSettings().notifications,
  );

  // `true` here (not a `ready` prop) is safe: this tab only ever mounts once
  // PortalSettingsPage's own usePortalGuard is already ready.
  const { settings, setSettings, saving, saved, error, handleSave } = usePortalSettings(true);
  const [offsetsError, setOffsetsError] = useState<string | null>(null);

  function patchNotification(key: keyof NotificationPreferencesMock) {
    setNotifications((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function handleResetPreferences() {
    setNotifications(initialGeneralSettings().notifications);
    toast.success("Reset to default", "Notification preferences reverted to their defaults.");
  }

  function handleSubmit(e: React.FormEvent) {
    const invalid = settings?.reminders_enabled
      ? validateReminderOffsetsHours(settings.reminder_offsets_hours)
      : null;
    if (invalid) {
      e.preventDefault();
      setOffsetsError(invalid);
      return;
    }
    setOffsetsError(null);
    handleSave(e);
  }

  return (
    <form onSubmit={handleSubmit} className="gap-space-4 flex flex-col">
      <Card className="p-space-4">
        <SectionHeader
          icon={Bell}
          tint="clay"
          title="Notification Preferences"
          subtitle="Choose how and when to send notifications"
        />
        <div className="divide-line divide-y">
          {settings && (
            <>
              <ToggleRow
                label="Appointment Reminders"
                subtitle="WhatsApp reminder before both new and follow-up appointments"
                checked={settings.reminders_enabled}
                onChange={() =>
                  setSettings({ ...settings, reminders_enabled: !settings.reminders_enabled })
                }
              />
              {settings.reminders_enabled && (
                <div className="py-space-3 gap-space-3 grid grid-cols-1 sm:grid-cols-2">
                  <Field
                    label="Reminder offsets (comma-separated hours)"
                    htmlFor="reminder_offsets_hours"
                    className="mb-0"
                    error={offsetsError || undefined}
                    hint={
                      offsetsError
                        ? undefined
                        : "How many hours before the appointment a WhatsApp reminder goes out. e.g. 24,1 sends one a day before and one an hour before."
                    }
                  >
                    <Input
                      id="reminder_offsets_hours"
                      value={settings.reminder_offsets_hours}
                      invalid={!!offsetsError}
                      onChange={(e) => {
                        setOffsetsError(null);
                        setSettings({ ...settings, reminder_offsets_hours: e.target.value });
                      }}
                    />
                  </Field>
                  <Field
                    label="Reminder template name"
                    htmlFor="reminder_template_name"
                    className="mb-0"
                  >
                    <Input
                      id="reminder_template_name"
                      value={settings.reminder_template_name}
                      onChange={(e) =>
                        setSettings({ ...settings, reminder_template_name: e.target.value })
                      }
                    />
                  </Field>
                </div>
              )}
            </>
          )}
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

      <div className="gap-space-2 flex flex-wrap items-center justify-end">
        {error && <p className="text-error mr-auto text-[12.5px] font-medium">{error}</p>}
        {saved && !error && (
          <p className="text-success mr-auto text-[12.5px] font-medium">Saved.</p>
        )}
        <Button type="submit" disabled={saving || !settings}>
          {saving ? "Saving…" : "Save Changes"}
        </Button>
      </div>
    </form>
  );
}
