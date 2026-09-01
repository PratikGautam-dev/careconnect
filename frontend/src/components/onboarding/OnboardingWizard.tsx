"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  CheckSquare,
  Clock,
  CreditCard,
  LogIn,
  Mail,
  MessageSquarePlus,
  MousePointerClick,
  Phone,
  ShieldCheck,
  SquarePlus,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { HorizontalStepRail } from "@/components/ui/HorizontalStepRail";
import { submitOnboarding, type OnboardingSuccess } from "@/lib/api";
import { OnboardingSuccessScreen } from "./OnboardingSuccessScreen";
import { Step0DataConnection, validateStep0 } from "./steps/Step0DataConnection";
import { Step4AccessToken } from "./steps/Step4AccessToken";
import { Step5PhoneSecret, validateStep5 } from "./steps/Step5PhoneSecret";
import { Step6PatientExperience, validateStep6 } from "./steps/Step6PatientExperience";
import { Step7HospitalDetails, validateStep7 } from "./steps/Step7HospitalDetails";
import { Step8Review } from "./steps/Step8Review";
import { StepGuide } from "./steps/StepGuide";
import { RAIL_TITLES, buildSubmissionPayload } from "./types";
import { useWizardState } from "./useWizardState";
import { getUserToken } from "@/lib/userAuth";
import { getAdminToken } from "@/lib/adminAuth";

const TOTAL_STEPS = RAIL_TITLES.length;

export function OnboardingWizard() {
  const router = useRouter();
  const [state, dispatch] = useWizardState();
  const [currentStep, setCurrentStep] = useState(0);
  const [maxUnlockedStep, setMaxUnlockedStep] = useState(0);
  const [stepError, setStepError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitErrors, setSubmitErrors] = useState<string[]>([]);
  const [success, setSuccess] = useState<OnboardingSuccess | null>(null);

  // Section 15: this wizard is only reachable after Google sign-in now (the
  // landing page CTA goes through /auth first) -- a direct visit with no
  // user session (e.g. a stale bookmark) gets bounced back there rather
  // than letting the form fill out only to fail at the final submit.
  useEffect(() => {
    if (!getUserToken()) router.replace("/auth");
  }, [router]);

  // Landing page's "Set up your clinic" button stashes this before sending
  // someone through the Google OAuth round-trip (/auth -> Google -> /auth/
  // callback -> here) -- sessionStorage survives that full-page navigation
  // within the same tab, unlike a query param on this page (Google's
  // redirect back only carries a token, not our own state). Routed through
  // the same "setTenantType" action Step7's own picker uses, not set
  // directly on the initial state, so the department/doctor seeding that
  // action performs runs exactly once, consistently, from a single place.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (sessionStorage.getItem("onboarding_intent") === "clinic") {
      sessionStorage.removeItem("onboarding_intent");
      dispatch({ type: "setTenantType", value: "clinic" });
    }
  }, [dispatch]);

  // goToStep is for rail clicks, gated by maxUnlockedStep already committed to
  // state from a previous render. handleNext must NOT route through it --
  // setMaxUnlockedStep(next) hasn't landed yet in this synchronous tick, so a
  // same-tick read of maxUnlockedStep here would still see the old value and
  // wrongly block the very advance that just unlocked it.
  function goToStep(step: number) {
    if (step > maxUnlockedStep) return;
    setCurrentStep(step);
    setStepError(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function handleNext() {
    let error: string | null = null;
    if (currentStep === 0) error = validateStep0(state);
    if (currentStep === 5) error = validateStep5(state);
    if (currentStep === 6) error = validateStep6(state);
    if (currentStep === 7) error = validateStep7(state);
    if (error) {
      setStepError(error);
      return;
    }
    setStepError(null);
    const next = currentStep + 1;
    setMaxUnlockedStep((prev) => Math.max(prev, next));
    setCurrentStep(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleSubmit() {
    setSubmitting(true);
    setSubmitErrors([]);
    // RBAC (docs/rbac-redis-plan.md): super_admin_token replaces the old
    // admin_secret wizard field -- this page is now gated behind
    // AdminSecretGate (see app/admin/onboard-hospital/page.tsx), so the
    // operator's own super-admin session token is already sitting in
    // lib/adminAuth.ts by the time anyone reaches this step.
    const payload = { ...buildSubmissionPayload(state), super_admin_token: getAdminToken() || "" };
    const result = await submitOnboarding(payload, getUserToken());
    setSubmitting(false);
    if (result.ok) {
      setSuccess(result.data);
    } else {
      setSubmitErrors(result.data.errors?.length ? result.data.errors : ["Something went wrong. Please try again."]);
    }
  }

  if (success) return <OnboardingSuccessScreen result={success} />;

  const isGuideStep = currentStep >= 1 && currentStep <= 3;
  const guideDone =
    currentStep === 1 ? state.metaAccountDone : currentStep === 2 ? state.whatsappAppDone : state.verifyBusinessDone;
  const nextDisabled = isGuideStep && !guideDone;

  return (
    <div className="px-space-4 py-space-7 md:px-space-7 lg:px-space-9">
      <div className="mb-space-5 flex flex-wrap items-center justify-between gap-space-3">
        <div className="flex items-center gap-space-2">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand-600 font-display text-[15px] font-extrabold text-white">
            H
          </div>
          <div className="min-w-0">
            <span className="block truncate text-[13px] font-bold text-ink-900">Hospital Onboarding</span>
            <span className="block text-[11px] text-ink-400">Guided setup wizard</span>
          </div>
        </div>
        <span className="rounded-full bg-brand-50 px-space-3 py-1 text-[12px] font-bold text-brand-700">
          Step {currentStep + 1} of {TOTAL_STEPS}
        </span>
      </div>

      <Card className="p-space-5 sm:p-space-6">
        <HorizontalStepRail
          steps={RAIL_TITLES.map((title) => ({ title }))}
          currentStep={currentStep}
          maxUnlockedStep={maxUnlockedStep}
          onStepClick={goToStep}
          className="mb-space-6"
        />

        {currentStep === 0 && <Step0DataConnection state={state} dispatch={dispatch} />}

        {currentStep === 1 && (
          <StepGuide
            stepNumber={1}
            title="Create a Meta Business Account"
            description="This is the account Meta uses to identify the hospital as a real business before it can send WhatsApp messages."
            duration="Takes about 2 minutes"
            instructions={[
              {
                icon: MousePointerClick,
                title: "Click Create Account",
                description: "Click Create Account (top right).",
              },
              {
                icon: Building2,
                title: "Enter your details",
                description: "Enter your hospital's name, your own name, and your work email.",
              },
              {
                icon: Mail,
                title: "Verify your email",
                description: "Check your email inbox and click the verification link Meta sends you.",
              },
              {
                icon: CheckSquare,
                title: "Return to this wizard",
                description: "Come back to this wizard and check the box below once done.",
              },
            ]}
            illustrationImageSrc="/onboarding-overview.png"
            illustrationImageAlt="Meta Business Suite walkthrough: click Create Account, enter your business details, verify your email, then return to this wizard and check the box below."
            resourceLink={{
              title: "Meta Business",
              description: "Open Meta Business Suite to create your account",
              displayUrl: "business.facebook.com",
              href: "https://business.facebook.com",
            }}
            done={state.metaAccountDone}
            onDoneChange={(v) => dispatch({ type: "set", field: "metaAccountDone", value: v })}
          />
        )}

        {currentStep === 2 && (
          <StepGuide
            stepNumber={2}
            title="Set up WhatsApp on a Meta app"
            description="The app is where the hospital's WhatsApp number and messaging permissions actually live."
            duration="Takes about 3 minutes"
            instructions={[
              {
                icon: LogIn,
                title: "Log in with the same account",
                description: "Use the same account you used in Step 1.",
              },
              {
                icon: SquarePlus,
                title: "Create your app",
                description:
                  'My Apps → Create App, choose Business as the type, give it any name, add a contact email.',
              },
              {
                icon: MessageSquarePlus,
                title: "Add WhatsApp to your app",
                description: "On the app dashboard, find WhatsApp under Add Products to Your App → click Set Up.",
              },
              {
                icon: ArrowRight,
                title: "Note the API Setup page",
                description: "You'll come back here in Step 5 to copy two values.",
              },
            ]}
            illustrationImageSrc="/meta-app-setup.png"
            illustrationImageAlt="Meta for Developers walkthrough: log in with the same account, create your app, add WhatsApp to your app, then note the API Setup page for Step 5."
            resourceLink={{
              title: "Meta for Developers",
              description: "Open your app dashboard to add WhatsApp",
              displayUrl: "developers.facebook.com",
              href: "https://developers.facebook.com",
            }}
            done={state.whatsappAppDone}
            onDoneChange={(v) => dispatch({ type: "set", field: "whatsappAppDone", value: v })}
          />
        )}

        {currentStep === 3 && (
          <StepGuide
            stepNumber={3}
            title="Verify business, register number, add payment"
            description="Genuine per-hospital steps on Meta's side — no wizard can skip these."
            duration="Can take a few hours to a few days"
            instructions={[
              {
                icon: ShieldCheck,
                title: "Start business verification",
                description: "Security Center → Start Verification, with your legal business name, address, and a document.",
              },
              {
                icon: Clock,
                title: "Wait for Meta's review",
                description: "Can take hours to days — you can continue with later wizard steps while you wait.",
              },
              {
                icon: Phone,
                title: "Register your number",
                description: "Add your hospital's real WhatsApp number and verify it via the code Meta texts you.",
              },
              {
                icon: CreditCard,
                title: "Add a payment method",
                description: "Required before sending messages; you're only charged for messages actually sent.",
              },
            ]}
            illustrationImageSrc="/meta-verify-payment.png"
            illustrationImageAlt="Meta Production Setup walkthrough: start business verification, wait for Meta's review, register your WhatsApp number, then add a payment method."
            illustrationImageWidth={1584}
            illustrationImageHeight={993}
            resourceLink={{
              title: "Meta for Developers",
              description: "Open your app's Production Setup to verify, register your number, and add payment",
              displayUrl: "developers.facebook.com",
              href: "https://developers.facebook.com",
            }}
            done={state.verifyBusinessDone}
            onDoneChange={(v) => dispatch({ type: "set", field: "verifyBusinessDone", value: v })}
          />
        )}

        {currentStep === 4 && <Step4AccessToken state={state} dispatch={dispatch} />}
        {currentStep === 5 && <Step5PhoneSecret state={state} dispatch={dispatch} error={stepError || undefined} />}
        {currentStep === 6 && (
          <Step6PatientExperience state={state} dispatch={dispatch} error={stepError || undefined} />
        )}
        {currentStep === 7 && <Step7HospitalDetails state={state} dispatch={dispatch} error={stepError || undefined} />}
        {currentStep === 8 && (
          <Step8Review
            state={state}
            dispatch={dispatch}
            onGoToStep={goToStep}
            onSubmit={handleSubmit}
            submitting={submitting}
            submitErrors={submitErrors}
          />
        )}

        {stepError && currentStep !== 5 && currentStep !== 6 && currentStep !== 7 && (
          <p className="mt-space-3 text-[12.5px] font-medium text-error">{stepError}</p>
        )}

        {currentStep !== 8 && (
          <div className="mt-space-6 flex items-center justify-between border-t border-line pt-space-4">
            {currentStep > 0 ? (
              <Button variant="secondary" onClick={() => goToStep(currentStep - 1)}>
                <ArrowLeft size={15} /> Previous
              </Button>
            ) : (
              <span />
            )}
            <span className="hidden text-[12.5px] text-ink-400 sm:block">
              Step {currentStep + 1} of {TOTAL_STEPS}
            </span>
            <Button onClick={handleNext} disabled={nextDisabled}>
              Continue <ArrowRight size={15} />
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
