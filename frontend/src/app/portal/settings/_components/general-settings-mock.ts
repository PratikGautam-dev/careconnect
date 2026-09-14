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

// "Advance Booking Limit" isn't here -- it's the real `future_booking_days`
// settings field (usePortalSettings), wired directly in GeneralSettingsTab
// instead of duplicated as mock state. Same for "Default Appointment
// Duration" / "Buffer Time Between Appointments" / "Maximum Appointments
// Per Day" (migration 20260914120000) -- all three are now real,
// backend-enforced settings (default_appointment_duration_minutes/
// buffer_minutes/max_appointments_per_day), not mock state either.
export type AppointmentSettingsMock = {
  allowOnlineAppointments: boolean;
  sendReminders: boolean;
};

export type NotificationPreferencesMock = {
  appointmentConfirmations: boolean;
  appointmentReminders: boolean;
  followUpReminders: boolean;
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
  appointments: AppointmentSettingsMock;
  notifications: NotificationPreferencesMock;
  security: SecuritySettingsMock;
};

/** Seed values for the General settings tab -- mirrors the reference
 * screenshot exactly. None of this is backed by a real endpoint yet (unlike
 * /portal/settings' existing form, see _reference/legacy-general-settings-
 * page.tsx), so it's local state the tab itself owns; Save/Reset just reset
 * this object, they don't call the API. */
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
    appointments: {
      allowOnlineAppointments: true,
      sendReminders: true,
    },
    notifications: {
      appointmentConfirmations: true,
      appointmentReminders: true,
      followUpReminders: true,
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

// Both now drive the real default_appointment_duration_minutes/
// buffer_minutes settings fields (migration 20260914120000) -- kept as
// preset dropdown options, same "not exhaustive, withValue() adds the
// current real value in if it's not one of these" convention as
// ADVANCE_BOOKING_DAYS_OPTIONS/SESSION_TIMEOUT_OPTIONS below.
export const DURATION_MINUTES_OPTIONS = [15, 30, 45, 60];
export const BUFFER_MINUTES_OPTIONS = [0, 5, 10, 15, 30];
// Capped at 90 -- the real `future_booking_days` field this drives
// enforces "between 1 and 90 days ahead" server-side.
export const ADVANCE_BOOKING_DAYS_OPTIONS = [30, 60, 90];
export const SESSION_TIMEOUT_OPTIONS = [15, 30, 60, 120];
export const PASSWORD_EXPIRY_OPTIONS = [30, 60, 90, 180];
