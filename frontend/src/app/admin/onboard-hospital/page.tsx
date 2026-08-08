import type { Metadata } from "next";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";

export const metadata: Metadata = {
  title: "Onboard a hospital — DAAP CareConnect",
};

export default function OnboardHospitalPage() {
  return (
    <div className="min-h-screen bg-paper">
      <OnboardingWizard />
    </div>
  );
}
