"use client";

import { Button } from "@/components/ui/Button";

// Landing page (a Server Component) can't define an inline onClick itself --
// event handlers only work inside a Client Component boundary, hence this
// tiny wrapper instead of adding one directly to page.tsx. Stashes the
// clinic intent in sessionStorage before the Google OAuth round-trip
// (/auth -> Google -> /auth/callback -> the onboarding wizard); the wizard
// reads and clears this flag on mount (OnboardingWizard.tsx) to preset
// "Clinic" instead of defaulting to "Hospital" -- same wizard, same /auth
// entry point, just a different starting selection.
export function ClinicSetupButton({
  variant = "primary",
  size = "lg",
}: {
  variant?: "primary" | "secondary" | "ghost";
  size?: "md" | "lg";
}) {
  return (
    <Button
      href="/auth"
      variant={variant}
      size={size}
      onClick={() => {
        try {
          sessionStorage.setItem("onboarding_intent", "clinic");
        } catch {
          // Private-browsing/storage-blocked edge case -- the wizard just
          // defaults to "Hospital" as it always did, no functional break.
        }
      }}
    >
      Set up your clinic
    </Button>
  );
}
