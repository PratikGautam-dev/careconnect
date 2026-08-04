const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type OnboardingSuccess = {
  hospital_id: number;
  hospital_name: string;
  whatsapp_phone_number_id: string;
  data_tier: string;
  portal_password_set: boolean;
  warnings: string[];
};

export type OnboardingFailure = {
  errors: string[];
  warnings?: string[];
};

export async function submitOnboarding(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload: Record<string, any>,
): Promise<{ ok: true; data: OnboardingSuccess } | { ok: false; data: OnboardingFailure }> {
  const res = await fetch(`${API_BASE_URL}/api/onboarding`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (res.ok) return { ok: true, data };
  return { ok: false, data };
}
