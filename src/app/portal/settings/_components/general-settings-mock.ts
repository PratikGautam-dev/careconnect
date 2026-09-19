export type HospitalBranding = {
  primaryColor: string;
  secondaryColor: string;
  tagline: string;
};

export type WhatsAppConfig = {
  enabled: boolean;
  businessNumber: string;
  apiKey: string;
  connected: boolean;
  lastSyncedAt: string;
};

// Advance Booking Limit, Default Appointment Duration, Buffer Time Between
// Appointments, and Maximum Appointments Per Day are real backend-enforced
// settings (usePortalSettings), wired directly in GeneralSettingsTab
// instead of duplicated as mock state here. Reminders on/off used to be a
// mock toggle here too (sendReminders) -- moved to the real, single
// `reminders_enabled` settings field (Notifications tab's "Appointment
// Reminders" toggle) instead of staying a disconnected duplicate.
// "Allow Online Appointments" used to be the last mock field here
// (allowOnlineAppointments) -- now the real `allow_online_appointments`
// settings field plus `booking_closure_from_date`/`booking_closure_to_date`/
// `closing_message_text`, since it drives an actual WhatsApp-side booking
// closure, wired directly in GeneralSettingsTab. Nothing mock-only is left
// for Appointment Settings, so there's no AppointmentSettingsMock type anymore.

// Appointment Reminders/Follow-up Reminders used to be mock toggles here
// too -- both merged into the one real `reminders_enabled` settings field
// (Notifications tab's "Message Templates & Content" card) instead, since
// reminders/scheduler.py already covers both appointment kinds with no
// separate mechanism to gate independently.
export type NotificationPreferencesMock = {
  labReportNotifications: boolean;
  systemAnnouncements: boolean;
  marketingCommunications: boolean;
};

// "Session Timeout" isn't here -- it's the real `session_timeout_minutes`
// settings field, wired directly in GeneralSettingsTab instead of
// duplicated as mock state (same reason as advanceBookingDays above).
export type SecuritySettingsMock = {
  passwordExpiryDays: number;
  allowMultipleSessions: boolean;
  logUserActivities: boolean;
};

export type GeneralSettingsState = {
  branding: HospitalBranding;
  whatsapp: WhatsAppConfig;
  notifications: NotificationPreferencesMock;
  security: SecuritySettingsMock;
};

/** Seed values for the General settings tab. None of this is backed by a
 * real endpoint yet, so it's local state the tab itself owns; Save/Reset
 * just reset this object, they don't call the API. */
export function initialGeneralSettings(): GeneralSettingsState {
  return {
    branding: {
      primaryColor: "#0D7C86",
      secondaryColor: "#0F2D5B",
      tagline: "Better Healthcare. Stronger Connection.",
    },
    whatsapp: {
      enabled: true,
      businessNumber: "+91 98765 43210",
      apiKey: "wa_live_9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c",
      connected: true,
      lastSyncedAt: "9 Sep 2026, 10:24 AM",
    },
    notifications: {
      labReportNotifications: true,
      systemAnnouncements: true,
      marketingCommunications: false,
    },
    security: {
      passwordExpiryDays: 90,
      allowMultipleSessions: false,
      logUserActivities: true,
    },
  };
}

// Preset dropdown options for default_appointment_duration_minutes/
// buffer_minutes -- not exhaustive; withValue() adds the current real
// value in if it's not one of these, same convention as
// ADVANCE_BOOKING_DAYS_OPTIONS/SESSION_TIMEOUT_OPTIONS below.
export const DURATION_MINUTES_OPTIONS = [15, 30, 45, 60];
export const BUFFER_MINUTES_OPTIONS = [0, 5, 10, 15, 30];
// Capped at 90 -- the real `future_booking_days` field this drives
// enforces "between 1 and 90 days ahead" server-side.
export const ADVANCE_BOOKING_DAYS_OPTIONS = [30, 60, 90];
export const SESSION_TIMEOUT_OPTIONS = [15, 30, 60, 120];
export const PASSWORD_EXPIRY_OPTIONS = [30, 60, 90, 180];
