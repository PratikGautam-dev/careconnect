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
      <div className="pointer-events-none absolute top-4 right-4 left-4 h-0.5 bg-line">
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
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 bg-card text-[12px] font-bold transition-colors duration-150",
                  isActive && "border-ink-900 bg-ink-900 text-white",
                  !isActive && isDone && "border-brand-600 bg-brand-600 text-white",
                  !isActive && !isDone && "border-line bg-card text-ink-400",
                )}
              >
                {isDone && !isActive ? <Check size={13} strokeWidth={3} /> : i}
              </span>
              <span
                className={cn(
                  "text-[11.5px] leading-tight font-semibold",
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
