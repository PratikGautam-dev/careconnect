export type DataTier = "tier1" | "tier2" | "tier3";

export type TenantType = "hospital" | "clinic";

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;
export type Weekday = (typeof WEEKDAYS)[number];

export type TimeRange = { start: string; end: string };

export type DoctorForm = {
  name: string;
  specialization: string;
  qualification: string;
  yearsExperience: string;
  workingDays: string[];
  shifts: TimeRange[];
  slotDurationMinutes: string;
  breaks: TimeRange[];
  maxBookingsPerSlot: string;
  dailyBookingLimit: string;
  onlineQuota: string;
  walkinQuota: string;
  followupDurationMinutes: string;
  effectiveFrom: string;
};

export type DepartmentForm = {
  name: string;
  doctors: DoctorForm[];
};

export type TopicForm = {
  topicLabel: string;
  answerText: string;
};

export type FeatureKey =
  | "booking"
  | "reschedule"
  | "cancel"
  | "view_appointments"
  | "reports_prescriptions"
  | "manage_patients"
  | "consent_privacy"
  | "hospital_info"
  | "reception_handoff"
  | "faq";

export type WizardState = {
  dataTier: DataTier;
  apiBaseUrl: string;
  apiKey: string;
  metaAccountDone: boolean;
  whatsappAppDone: boolean;
  verifyBusinessDone: boolean;
  accessToken: string;
  whatsappPhoneNumberId: string;
  appSecret: string;
  enabledFeatures: FeatureKey[];
  tenantType: TenantType;
  name: string;
  welcomeMessageText: string;
  reminderOffsetsHours: string;
  reminderTemplateName: string;
  portalPassword: string;
  departments: DepartmentForm[];
  topics: TopicForm[];
  // RBAC (docs/rbac-redis-plan.md): this hospital's first staff_users admin
  // login -- replaces the old shared portalPassword as the real ongoing
  // login. portalPassword above is still collected/sent (still accepted
  // during the dual-path migration window) but is no longer the field
  // required for onboarding to succeed.
  adminEmail: string;
  adminPassword: string;
};

export function emptyDoctor(): DoctorForm {
  return {
    name: "",
    specialization: "",
    qualification: "",
    yearsExperience: "",
    workingDays: [],
    shifts: [{ start: "", end: "" }],
    slotDurationMinutes: "",
    breaks: [],
    maxBookingsPerSlot: "1",
    dailyBookingLimit: "",
    onlineQuota: "",
    walkinQuota: "",
    followupDurationMinutes: "",
    effectiveFrom: "",
  };
}

export function emptyDepartment(): DepartmentForm {
  return { name: "", doctors: [] };
}

export function emptyTopic(): TopicForm {
  return { topicLabel: "", answerText: "" };
}

export function initialWizardState(): WizardState {
  return {
    dataTier: "tier1",
    apiBaseUrl: "",
    apiKey: "",
    metaAccountDone: false,
    whatsappAppDone: false,
    verifyBusinessDone: false,
    accessToken: "",
    whatsappPhoneNumberId: "",
    appSecret: "",
    enabledFeatures: ["booking", "reschedule", "cancel", "view_appointments", "hospital_info", "reception_handoff"],
    tenantType: "hospital",
    name: "",
    welcomeMessageText: "",
    reminderOffsetsHours: "24",
    reminderTemplateName: "",
    portalPassword: "",
    departments: [],
    topics: [],
    adminEmail: "",
    adminPassword: "",
  };
}

export const RAIL_TITLES = [
  "Data Connection",
  "Business Account",
  "WhatsApp on Meta",
  "Verify Business",
  "Access Token",
  "Phone & App Secret",
  "Patient Experience",
  "Hospital Details",
  "Review & Submit",
];

export const FEATURE_LABELS: Record<FeatureKey, string> = {
  booking: "Book Appointment",
  reschedule: "Reschedule Appointment",
  cancel: "Cancel Appointment",
  view_appointments: "View My Appointments",
  reports_prescriptions: "Reports & Prescriptions",
  manage_patients: "Manage Patients",
  consent_privacy: "Consent & Privacy",
  hospital_info: "Hospital Information",
  reception_handoff: "Talk to Reception",
  faq: "FAQ / Information Bot",
};

/** Builds the JSON payload the FastAPI /api/onboarding endpoint expects --
 * shift/break TimeRange pairs collapse into "HH:MM-HH:MM" strings here, the
 * one place that format matters, so every step component upstream can work
 * with plain structured objects instead of that string format. */
export function buildSubmissionPayload(state: WizardState) {
  return {
    // super_admin_token is NOT read off `state` here -- it's the platform
    // operator's own super-admin session (lib/adminAuth.ts), not part of
    // the wizard's persisted form state, so OnboardingWizard's submit
    // handler merges it into this object right before POSTing (same
    // pattern getUserToken() already follows for the Google-auth header).
    tenant_type: state.tenantType,
    name: state.name,
    whatsapp_phone_number_id: state.whatsappPhoneNumberId,
    access_token: state.accessToken,
    app_secret: state.appSecret,
    welcome_message_text: state.welcomeMessageText,
    reminder_offsets_hours: state.reminderOffsetsHours,
    reminder_template_name: state.reminderTemplateName,
    portal_password: state.portalPassword,
    admin_email: state.adminEmail,
    admin_password: state.adminPassword,
    enabled_features: state.enabledFeatures,
    data_tier: state.dataTier,
    api_base_url: state.apiBaseUrl,
    api_key: state.apiKey,
    departments: state.departments.map((dept) => ({
      name: dept.name,
      doctors: dept.doctors.map((doc) => ({
        name: doc.name,
        specialization: doc.specialization,
        qualification: doc.qualification,
        years_experience: doc.yearsExperience,
        working_days: doc.workingDays,
        working_hours: doc.shifts.filter((s) => s.start && s.end).map((s) => `${s.start}-${s.end}`),
        slot_duration_minutes: doc.slotDurationMinutes,
        breaks: doc.breaks.filter((b) => b.start && b.end).map((b) => `${b.start}-${b.end}`),
        max_bookings_per_slot: doc.maxBookingsPerSlot,
        daily_booking_limit: doc.dailyBookingLimit,
        online_quota: doc.onlineQuota,
        walkin_quota: doc.walkinQuota,
        followup_duration_minutes: doc.followupDurationMinutes,
        effective_from: doc.effectiveFrom,
      })),
    })),
    topics: state.topics.map((t) => ({ topic_label: t.topicLabel, answer_text: t.answerText })),
  };
}
