// Language and Business Hours aren't here -- they're the real
// `default_language`/`language_prompt_enabled`/`business_hours_text`
// settings fields (usePortalSettings), wired directly in GeneralSettingsTab
// instead of duplicated as mock state (same reason as advanceBookingDays/
// sessionTimeoutMinutes below).
export type HospitalInfo = {
  name: string;
  address: string;
  phone: string;
  email: string;
  timezone: string;
  dateFormat: string;
};

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
// instead of duplicated as mock state.
export type AppointmentSettingsMock = {
  defaultDurationMinutes: number;
  bufferMinutes: number;
  maxAppointmentsPerDay: number;
  allowOnlineAppointments: boolean;
  requireApproval: boolean;
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
  requireTwoFactor: boolean;
  enforceStrongPassword: boolean;
  allowMultipleSessions: boolean;
  logUserActivities: boolean;
};

export type GeneralSettingsState = {
  hospitalInfo: HospitalInfo;
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
    hospitalInfo: {
      name: "DAAP CareConnect Hospital",
      address: "123 Health Avenue, Medical District\nNew Delhi, Delhi 110001, India",
      phone: "+91 11 2345 6789",
      email: "admin@daapcareconnect.com",
      timezone: "(GMT+05:30) Asia/Kolkata",
      dateFormat: "DD/MM/YYYY",
    },
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
      defaultDurationMinutes: 30,
      bufferMinutes: 10,
      maxAppointmentsPerDay: 50,
      allowOnlineAppointments: true,
      requireApproval: false,
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
      requireTwoFactor: true,
      enforceStrongPassword: true,
      allowMultipleSessions: false,
      logUserActivities: true,
    },
  };
}

export const TIMEZONE_OPTIONS = [
  "(GMT+05:30) Asia/Kolkata",
  "(GMT+00:00) UTC",
  "(GMT-05:00) America/New_York",
  "(GMT+01:00) Europe/London",
];

export const DATE_FORMAT_OPTIONS = ["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"];

export const DURATION_MINUTES_OPTIONS = [15, 30, 45, 60];
export const BUFFER_MINUTES_OPTIONS = [0, 5, 10, 15, 30];
// Capped at 90 -- the real `future_booking_days` field this drives
// enforces "between 1 and 90 days ahead" server-side.
export const ADVANCE_BOOKING_DAYS_OPTIONS = [30, 60, 90];
export const MAX_PER_DAY_OPTIONS = [20, 50, 100, 200];
export const SESSION_TIMEOUT_OPTIONS = [15, 30, 60, 120];
export const PASSWORD_EXPIRY_OPTIONS = [30, 60, 90, 180];
