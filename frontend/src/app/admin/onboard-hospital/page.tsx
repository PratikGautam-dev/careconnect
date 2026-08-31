import type { Metadata } from "next";
import { AdminSecretGate } from "@/components/admin/AdminSecretGate";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";

export const metadata: Metadata = {
  title: "Onboard a hospital — DAAP CareConnect",
};

export default function OnboardHospitalPage() {
  return (
    <AdminSecretGate title="Super admin sign-in">
      <div className="min-h-screen bg-paper">
        <OnboardingWizard />
      </div>
    </AdminSecretGate>
  );
}
