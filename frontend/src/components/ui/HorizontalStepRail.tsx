import { Check } from "lucide-react";
import { cn } from "@/lib/cn";
import type { StepRailItem } from "./StepRail";

type HorizontalStepRailProps = {
  steps: StepRailItem[];
  currentStep: number;
  maxUnlockedStep: number;
  onStepClick: (step: number) => void;
  className?: string;
};

export function HorizontalStepRail({
  steps,
  currentStep,
  maxUnlockedStep,
  onStepClick,
  className,
}: HorizontalStepRailProps) {
  const total = steps.length;
  const progressPercent = total > 1 ? (currentStep / (total - 1)) * 100 : 0;

  return (
    <nav className={cn("relative", className)} aria-label="Onboarding steps">
      <div className="pointer-events-none absolute top-3.5 right-4 left-4 h-0.5 bg-line md:top-4">
        <div
          className="h-full bg-brand-600 transition-[width] duration-300 ease-(--ease-standard)"
          style={{ width: `${progressPercent}%` }}
        />
      </div>
      <div className="relative flex items-start justify-between">
        {steps.map((step, i) => {
          const isDone = i < maxUnlockedStep;
          const isActive = i === currentStep;
          const isClickable = i <= maxUnlockedStep;
          return (
            <button
              key={step.title}
              type="button"
              disabled={!isClickable}
              onClick={() => onStepClick(i)}
              className={cn(
                "flex flex-1 flex-col items-center gap-space-2 px-1 text-center",
                isClickable ? "cursor-pointer" : "cursor-not-allowed",
              )}
            >
              <span
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 bg-card text-[11px] font-bold transition-colors duration-150 md:h-8 md:w-8 md:text-[12px]",
                  isActive && "border-ink-900 bg-ink-900 text-white",
                  !isActive && isDone && "border-brand-600 bg-brand-600 text-white",
                  !isActive && !isDone && "border-line bg-card text-ink-400",
                )}
              >
                {isDone && !isActive ? <Check size={13} strokeWidth={3} /> : i}
              </span>
              {/* Labels collide/wrap across 9 flex-1 items below ~768px --
                  the "Step X of N" badge above the rail (OnboardingWizard.tsx)
                  already gives mobile users that context, so the label here
                  is desktop-only rather than trying to fit 9 short strings
                  in the same cramped width. */}
              <span
                className={cn(
                  "hidden text-[11.5px] leading-tight font-semibold md:block",
                  isActive && "text-ink-900",
                  !isActive && isDone && "text-brand-700",
                  !isActive && !isDone && "text-ink-400",
                )}
              >
                {step.title}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
