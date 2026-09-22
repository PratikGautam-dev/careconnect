import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";

export type Settings = {
  name: string;
  welcome_message_text: string;
  reminder_offsets_hours: string;
  reminder_template_name: string;
  // Real on/off switch for WhatsApp appointment reminders (Settings ->
  // Notifications) -- reminder_offsets_hours stays configured either way;
  // turning this off just pauses the cron job's sending for this hospital.
  // Covers both new-consultation and follow-up appointment reminders.
  reminders_enabled: boolean;
  enabled_features: string[];
  // "Online booking closed" notice, shown when allow_online_appointments is
  // off and today falls inside [booking_closure_from_date,
  // booking_closure_to_date] (either bound blank = open-ended). Dates are
  // plain "YYYY-MM-DD" strings, "" meaning unset.
  closing_message_text: string;
  allow_online_appointments: boolean;
  booking_closure_from_date: string;
  booking_closure_to_date: string;
  business_hours_text: string;
  default_language: "en" | "hi";
  language_prompt_enabled: boolean;
  session_timeout_minutes: number;
  require_patient_confirmation: boolean;

  handoff_auto_resolve_hours: number;

  // Fees are "" (unset -- no fee line shown) or a numeric string, since a
  // plain `number` type can't represent "no value entered" as distinct from 0.
  followup_validity_days: number;
  followup_fee: number | "";
  new_consultation_fee: number | "";
  // Same "" (unset) convention as followup_fee/new_consultation_fee above --
  // tele-consultation and second-opinion booking types' own fees.
  tele_consultation_fee: number | "";
  second_opinion_fee: number | "";
  // Flat fee added to a home-collection Lab Test booking's price review,
  // same "" (unset) convention as the two fees above.
  home_collection_charge: number | "";
  // How many days ahead doctor/resource/procedure slots are generated --
  // always has a value (defaults server-side).
  future_booking_days: number;

  // default_appointment_duration_minutes/buffer_minutes always have a
  // value (30/0 code defaults). max_appointments_per_day uses the ""
  // (unset) convention like the fees above -- no cap configured is a real,
  // common state, not something to default away. appointments_today_count
  // is read-only, live data for the progress bar -- never sent back on save.
  default_appointment_duration_minutes: number;
  buffer_minutes: number;
  max_appointments_per_day: number | "";
  appointments_today_count: number;

  // Contact Information card (Settings -> General) -- plain display
  // details, `hospitals` columns (not hospital_settings). No `website`
  // field -- dropped rather than made real (confirmed with the user).
  contact_phone: string;
  contact_alternate_phone: string;
  contact_email: string;
  contact_address: string;
  emergency_contact_number: string;
  emergency_contact_person: string;
  emergency_contact_designation: string;
};

function normalizeSettings(
  data: Settings & {
    followup_fee: number | null;
    new_consultation_fee: number | null;
    tele_consultation_fee: number | null;
    second_opinion_fee: number | null;
    home_collection_charge: number | null;
    max_appointments_per_day: number | null;
  },
): Settings {
  // Coerced to "" here so the numeric <Input> below never renders "null".
  return {
    ...data,
    followup_fee: data.followup_fee ?? "",
    new_consultation_fee: data.new_consultation_fee ?? "",
    tele_consultation_fee: data.tele_consultation_fee ?? "",
    second_opinion_fee: data.second_opinion_fee ?? "",
    home_collection_charge: data.home_collection_charge ?? "",
    max_appointments_per_day: data.max_appointments_per_day ?? "",
  };
}

/** Loads + saves the /portal/settings form. */
export function usePortalSettings(ready: boolean) {
  const router = useRouter();

  const {
    data: loadedSettings,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey: ["portal-settings"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/settings");
      const data = unwrapPortalResult<
        Settings & {
          followup_fee: number | null;
          new_consultation_fee: number | null;
          tele_consultation_fee: number | null;
          second_opinion_fee: number | null;
          home_collection_charge: number | null;
          max_appointments_per_day: number | null;
        }
      >(router, result);
      return normalizeSettings(data);
    },
  });

  // Editable draft, seeded once per successful load -- edits here (via
  // setSettings) shouldn't be clobbered by a background refetch of the same
  // query, same shape useAttendanceSettings.ts's own draft uses.
  const [seeded, setSeeded] = useState(false);
  const [settings, setSettings] = useState<Settings | null>(null);
  if (loadedSettings && !seeded) {
    setSeeded(true);
    setSettings(loadedSettings);
  }

  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: async (payload: Settings) => {
      const result = await portalFetch("/api/portal/settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setSaved(false);
    setSaveError(null);
    try {
      await saveMutation.mutateAsync(settings);
      // The backend can NORMALIZE a submitted value (e.g. an emptied/garbled
      // "Reminder offsets" field is coerced to a default of "24") without
      // the page finding out, so re-fetch here rather than trusting the
      // just-submitted `settings` object, keeping displayed values in sync
      // with what was actually persisted.
      const { data: refreshed } = await refetch();
      if (refreshed) setSettings(refreshed);
      setSaved(true);
      toast.success("Settings saved");
    } catch (err) {
      if (isPortalMutationError(err)) {
        setSaveError(err.message);
        toast.error("Couldn't save settings", err.message);
      }
    }
  }

  return {
    settings,
    setSettings,
    error: saveError ?? (queryError ? "Couldn't load settings — try again." : null),
    saving: saveMutation.isPending,
    saved,
    handleSave,
  };
}
